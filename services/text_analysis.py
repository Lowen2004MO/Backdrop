import math
import re
from collections import Counter, defaultdict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.pulse.models import (
    ImportedAnswer,
    TextAnnotation,
    TextTheme,
)


MODEL_VERSION = 'local-hybrid-embedding-v1'
THEME_CATALOGUE = {
    'Workload and capacity': (
        'Pace, workload, deadlines, staffing and competing priorities.',
        ('workload', 'capacity', 'deadline', 'busy', 'pressure', 'time', 'priorities', 'overwhelmed'),
    ),
    'Manager support': (
        'Manager availability, feedback, coaching and practical support.',
        ('manager', 'management', 'leadership', 'feedback', 'check-in', 'support'),
    ),
    'Career development': (
        'Training, learning, progression, promotion and development.',
        ('training', 'learning', 'career', 'progression', 'promotion', 'development', 'skills'),
    ),
    'Communication': (
        'Clarity, transparency, information sharing and decision communication.',
        ('communication', 'communicate', 'clarity', 'clear', 'information', 'transparent', 'updates'),
    ),
    'Tools and access': (
        'Systems, equipment, permissions, tooling and access.',
        ('tools', 'systems', 'system', 'access', 'permissions', 'equipment', 'software'),
    ),
    'Team connection': (
        'Collaboration, belonging, colleagues and cross-team relationships.',
        ('team', 'colleagues', 'collaboration', 'community', 'belonging', 'handover', 'remote'),
    ),
    'Organisational change': (
        'Acquisition, integration, restructuring and organisational uncertainty.',
        ('acquisition', 'acquired', 'buyout', 'integration', 'restructure', 'change', 'legacy'),
    ),
}
POSITIVE_WORDS = {
    'helpful', 'supported', 'excellent', 'good', 'great', 'clear', 'useful',
    'successful', 'positive', 'easy', 'excited', 'happy', 'improved',
}
NEGATIVE_WORDS = {
    'difficult', 'hard', 'unclear', 'frustrating', 'poor', 'bad', 'busy',
    'pressure', 'overwhelmed', 'waiting', 'problem', 'concern', 'changing',
}
STOPWORDS = {
    'about', 'after', 'again', 'also', 'and', 'answer', 'because', 'been',
    'before', 'could', 'from', 'have', 'into', 'more', 'not', 'that', 'their',
    'there', 'these', 'they', 'this', 'those', 'very', 'what', 'when', 'where',
    'which', 'while', 'with', 'would', 'your',
}
SEMANTIC_EXPANSIONS = {
    'application': ('software', 'system', 'tools'),
    'buyout': ('acquisition', 'integration', 'change'),
    'colleague': ('colleagues', 'team', 'community'),
    'coworker': ('colleagues', 'team', 'community'),
    'deadline': ('workload', 'pressure', 'time'),
    'leader': ('leadership', 'manager', 'management'),
    'merger': ('acquisition', 'integration', 'change'),
    'platform': ('software', 'system', 'tools'),
    'priority': ('priorities', 'workload', 'time'),
    'supervisor': ('manager', 'management', 'support'),
    'upskilling': ('training', 'learning', 'development'),
}


def _tokens(text):
    return re.findall(r'[a-z][a-z-]{2,}', text.casefold())


def _sentences(text):
    return [
        sentence.strip()
        for sentence in re.split(r'(?<=[.!?])\s+|[\r\n]+', text)
        if sentence.strip()
    ]


def _sentiment(sentence):
    words = set(_tokens(sentence))
    positive = len(words & POSITIVE_WORDS)
    negative = len(words & NEGATIVE_WORDS)
    if positive and negative:
        return 'mixed'
    if positive:
        return 'positive'
    if negative:
        return 'negative'
    return 'neutral'


def _embedding(text):
    features = []
    for word in _tokens(text):
        if word in STOPWORDS:
            continue
        features.append(word)
        features.extend(SEMANTIC_EXPANSIONS.get(word, ()))
    vector = Counter(features)
    magnitude = math.sqrt(sum(value * value for value in vector.values()))
    return {
        feature: value / magnitude for feature, value in vector.items()
    } if magnitude else {}


def _cosine(left, right):
    return sum(value * right.get(feature, 0) for feature, value in left.items())


def _match(sentence, keywords):
    lowered = sentence.casefold()
    words = set(_tokens(sentence))
    score = 0
    for keyword in keywords:
        if ' ' in keyword:
            score += 2 if keyword in lowered else 0
        elif keyword in words:
            score += 1
    similarity = _cosine(
        _embedding(sentence),
        _embedding(' '.join(keywords)),
    )
    return score, similarity


def _ensure_catalogue():
    themes = []
    for name, (description, keywords) in THEME_CATALOGUE.items():
        theme, _ = TextTheme.objects.update_or_create(
            survey_import=None,
            name=name,
            defaults={
                'description': description,
                'keywords': list(keywords),
                'status': 'reviewed',
            },
        )
        themes.append(theme)
    return themes


def _discover_terms(unmatched_by_response):
    response_terms = Counter()
    for terms in unmatched_by_response.values():
        response_terms.update(set(terms))
    return [
        term for term, count in response_terms.most_common(8)
        if count >= 2
    ][:3]


@transaction.atomic
def analyse_survey(survey):
    themes = _ensure_catalogue()
    themes.extend(
        survey.local_themes.filter(status='reviewed')
    )
    answers = (
        ImportedAnswer.objects.filter(
            response__survey_import=survey,
            question__response_type='written',
        )
        .exclude(value='')
        .select_related('response')
    )
    TextAnnotation.objects.filter(answer__in=answers).delete()
    annotations = []
    unmatched_by_response = defaultdict(list)
    for answer in answers:
        matched_any = False
        for sentence in _sentences(answer.value):
            sentence_matched = False
            for theme in themes:
                score, similarity = _match(sentence, theme.keywords)
                if not score and similarity < 0.20:
                    continue
                sentence_matched = True
                matched_any = True
                annotations.append(
                    TextAnnotation(
                        answer=answer,
                        theme=theme,
                        sentiment=_sentiment(sentence),
                        confidence=min(
                            95,
                            round(55 + score * 12 + similarity * 25),
                        ),
                        evidence=sentence,
                        model_version=MODEL_VERSION,
                    )
                )
            if not sentence_matched:
                unmatched_by_response[answer.response_id].extend(
                    word for word in _tokens(sentence)
                    if word not in STOPWORDS
                )
        if not matched_any:
            unmatched_by_response[answer.response_id].extend(
                word for word in _tokens(answer.value)
                if word not in STOPWORDS
            )
    # Keep the strongest evidence when multiple sentences map to one theme.
    strongest = {}
    for annotation in annotations:
        key = (annotation.answer_id, annotation.theme_id)
        if key not in strongest or annotation.confidence > strongest[key].confidence:
            strongest[key] = annotation
    TextAnnotation.objects.bulk_create(strongest.values())

    discovered = _discover_terms(unmatched_by_response)
    for term in discovered:
        TextTheme.objects.get_or_create(
            survey_import=survey,
            name=f'Suggested topic: {term.title()}',
            defaults={
                'description': 'Repeated language not covered by the reviewed theme catalogue.',
                'keywords': [term],
                'status': 'proposed',
            },
        )
    survey.text_analysis_version = MODEL_VERSION
    survey.text_analysed_at = timezone.now()
    survey.save(update_fields=('text_analysis_version', 'text_analysed_at'))
    return len(strongest)


def _is_negative(value, response_type):
    value = value.strip().casefold()
    if response_type == 'agreement':
        return value in ('disagree', 'strongly disagree')
    if response_type == 'binary':
        return value == 'no'
    if response_type == 'recommendation':
        try:
            return float(value) <= 6
        except ValueError:
            return False
    if response_type == 'rating':
        return value in ('uncomfortable', 'very uncomfortable', 'difficult', 'very difficult')
    return False


def survey_text_summary(survey):
    minimum = getattr(settings, 'PEOPLE_PULSE_MIN_COHORT_SIZE', 2)
    total = survey.response_count
    annotations = TextAnnotation.objects.filter(
        answer__response__survey_import=survey,
        theme__status='reviewed',
    ).select_related('theme', 'answer__response')
    by_theme = defaultdict(list)
    for annotation in annotations:
        by_theme[annotation.theme].append(annotation)
    themes = []
    for theme, items in by_theme.items():
        response_ids = {item.answer.response_id for item in items}
        sentiments = Counter(item.sentiment for item in items)
        themes.append({
            'theme': theme,
            'responses': len(response_ids),
            'prevalence': round(len(response_ids) * 100 / total) if total else 0,
            'sentiments': sentiments,
            'evidence': sorted(items, key=lambda item: -item.confidence)[:3],
        })
    themes.sort(key=lambda row: (-row['prevalence'], row['theme'].name))

    associations = []
    quantitative = survey.questions.filter(
        response_type__in=('agreement', 'binary', 'rating', 'recommendation')
    )
    for question in quantitative:
        answers = {
            answer.response_id: answer
            for answer in question.answers.exclude(value='')
        }
        for row in themes:
            mentioned = {
                item.answer.response_id for item in by_theme[row['theme']]
            } & set(answers)
            not_mentioned = set(answers) - mentioned
            if len(mentioned) < minimum or len(not_mentioned) < minimum:
                continue
            negative_with = sum(
                _is_negative(answers[item].value, question.response_type)
                for item in mentioned
            )
            negative_without = sum(
                _is_negative(answers[item].value, question.response_type)
                for item in not_mentioned
            )
            rate_with = round(negative_with * 100 / len(mentioned))
            rate_without = round(negative_without * 100 / len(not_mentioned))
            associations.append({
                'question': question,
                'theme': row['theme'],
                'mentioned': len(mentioned),
                'negative_rate_with': rate_with,
                'negative_rate_without': rate_without,
                'difference': rate_with - rate_without,
            })
    associations.sort(key=lambda row: (-abs(row['difference']), row['question'].text))

    periods = list(
        type(survey).objects.filter(name=survey.name).order_by(
            'financial_year', 'quarter'
        )
    )
    trends = []
    for row in themes:
        points = []
        for period in periods:
            mentioned = TextAnnotation.objects.filter(
                answer__response__survey_import=period,
                theme=row['theme'],
                theme__status='reviewed',
            ).values('answer__response_id').distinct().count()
            points.append({
                'survey': period,
                'prevalence': round(mentioned * 100 / period.response_count)
                if period.response_count else 0,
            })
        if any(point['prevalence'] for point in points):
            trends.append({'theme': row['theme'], 'points': points})

    dimension_comparisons = []
    for dimension in survey.questions.filter(is_dimension=True):
        group_rows = []
        for value in (
            dimension.answers.exclude(value='').order_by('value')
            .values_list('value', flat=True).distinct()
        ):
            response_ids = set(
                dimension.answers.filter(value=value)
                .values_list('response_id', flat=True)
            )
            if len(response_ids) < minimum:
                group_rows.append({
                    'value': value,
                    'responses': len(response_ids),
                    'suppressed': True,
                    'themes': [],
                })
                continue
            group_themes = []
            for row in themes:
                mentioned = {
                    item.answer.response_id for item in by_theme[row['theme']]
                } & response_ids
                group_themes.append({
                    'theme': row['theme'],
                    'prevalence': round(len(mentioned) * 100 / len(response_ids)),
                })
            group_rows.append({
                'value': value,
                'responses': len(response_ids),
                'suppressed': False,
                'themes': group_themes,
            })
        dimension_comparisons.append({
            'dimension': dimension,
            'groups': group_rows,
        })
    return {
        'theme_rows': themes,
        'associations': associations[:20],
        'trends': trends,
        'proposed_themes': survey.local_themes.filter(status='proposed'),
        'minimum_group_size': minimum,
        'model_version': survey.text_analysis_version,
        'dimension_comparisons': dimension_comparisons,
    }
