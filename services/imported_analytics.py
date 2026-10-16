from collections import Counter

from django.conf import settings

from apps.pulse.models import ImportedAnswer, ImportedQuestion, ImportedResponse, TextAnnotation
from services.question_mapping import normalize_question
from services.response_comparison import AGREEMENT_SCORES, answer_change
from services.distribution_comparison import add_period_changes


AGREEMENT_ORDER = (
    'Strongly disagree',
    'Disagree',
    'Neutral',
    'Agree',
    'Strongly agree',
)
BINARY_ORDER = ('Yes', 'No', 'Unsure', 'Not sure')


def _percentage_rows(counts, total):
    if not total:
        return [
            {'category': category, 'count': count, 'percentage': 0}
            for category, count in counts
        ]
    entries = list(counts)
    exact = [count * 100 / total for _, count in entries]
    percentages = [int(value) for value in exact]
    remainder = 100 - sum(percentages)
    order = sorted(range(len(entries)), key=lambda index: exact[index] - percentages[index], reverse=True)
    for index in order[:remainder]:
        percentages[index] += 1
    rows = [{'category': category, 'count': count, 'percentage': percentage}
            for (category, count), percentage in zip(entries, percentages)]
    return rows


def _distribution(question, cohort='', response_ids=None):
    total = question.survey_import.response_count
    answers = question.answers.all()
    if response_ids is not None:
        answers = answers.filter(response_id__in=response_ids)
        total = len(response_ids)
    elif cohort:
        answers = answers.filter(response__cohort=cohort)
        total = question.survey_import.responses.filter(cohort=cohort).count()
    values = list(answers.values_list('value', flat=True))
    populated = [value.strip() for value in values if value.strip()]
    missing = max(0, total - len(populated))

    if question.response_type == 'written':
        counts = [
            ('Response provided', len(populated)),
            ('No written response', missing),
        ]
    elif question.response_type == 'agreement':
        actual = Counter('neutral' if value.casefold() == 'neither agree nor disagree' else value.casefold() for value in populated)
        counts = [
            (label, actual.get(label.casefold(), 0))
            for label in AGREEMENT_ORDER
        ]
        unknown = len(populated) - sum(count for _, count in counts)
        if unknown:
            counts.append(('Other', unknown))
        counts.append(('Missing', missing))
    elif question.response_type == 'binary':
        actual = Counter(value.casefold() for value in populated)
        counts = [
            (label, actual.get(label.casefold(), 0))
            for label in BINARY_ORDER
        ]
        unknown = len(populated) - sum(count for _, count in counts)
        if unknown:
            counts.append(('Other', unknown))
        counts.append(('Missing', missing))
    elif question.response_type == 'recommendation':
        groups = Counter()
        for value in populated:
            try:
                score = float(value)
            except ValueError:
                groups['Other'] += 1
                continue
            if 0 <= score <= 6:
                groups['Detractor (0-6)'] += 1
            elif score <= 8:
                groups['Passive (7-8)'] += 1
            elif score <= 10:
                groups['Promoter (9-10)'] += 1
            else:
                groups['Other'] += 1
        counts = [
            (label, groups[label])
            for label in ('Detractor (0-6)', 'Passive (7-8)', 'Promoter (9-10)')
        ]
        if groups['Other']:
            counts.append(('Other', groups['Other']))
        counts.append(('Missing', missing))
    else:
        actual = Counter(populated)
        common = actual.most_common(7)
        represented = sum(count for _, count in common)
        counts = common
        if represented < len(populated):
            counts.append(('Other values', len(populated) - represented))
        counts.append(('Missing', missing))

    return _percentage_rows(counts, total)


def _metric(question, cohort='', response_ids=None):
    if not cohort and response_ids is None:
        return question.latest_positive
    answers = question.answers.all()
    if response_ids is not None:
        answers = answers.filter(response_id__in=response_ids)
        total = len(response_ids)
    else:
        answers = answers.filter(response__cohort=cohort)
        total = question.survey_import.responses.filter(cohort=cohort).count()
    values = list(answers.exclude(value='').values_list('value', flat=True))
    if not total:
        return 0
    normalised = [value.strip().casefold() for value in values]
    if question.response_type == 'agreement':
        count = sum(value in ('agree', 'strongly agree') for value in normalised)
    elif question.response_type == 'binary':
        count = sum(value == 'yes' for value in normalised)
    elif question.response_type == 'recommendation':
        count = 0
        for value in normalised:
            try:
                count += float(value) >= 9
            except ValueError:
                continue
    elif question.response_type == 'choice' and normalised:
        count = Counter(normalised).most_common(1)[0][1]
    else:
        count = len(values)
    return round(count * 100 / total)


def _aligned_rows(rows):
    categories = []
    for row in rows:
        for item in row['items']:
            if item['category'] not in categories:
                categories.append(item['category'])
    for row in rows:
        by_category = {item['category']: item for item in row['items']}
        row['items'] = [
            by_category.get(
                category,
                {'category': category, 'count': 0, 'percentage': 0},
            )
            for category in categories
        ]
    return rows


def _single_question_detail(question, groups=(), dimension_id=''):
    survey = question.survey_import
    dimensions = list(
        survey.questions.filter(is_dimension=True).exclude(pk=question.pk)
    )
    dimension = next(
        (item for item in dimensions if str(item.pk) == str(dimension_id)),
        next(
            (item for item in dimensions if item.canonical_slug == 'primary-area'),
            dimensions[0] if dimensions else None,
        ),
    )
    raw_groups = list(
        dimension.answers.exclude(value='').order_by('value')
        .values_list('value', flat=True).distinct()
    ) if dimension else []
    minimum = getattr(settings, 'PEOPLE_PULSE_MIN_COHORT_SIZE', 2)
    group_counts = {
        group: dimension.answers.filter(value=group).count()
        for group in raw_groups
    } if dimension else {}
    available_groups = [
        group for group in raw_groups if group_counts[group] >= minimum
    ]
    suppressed_groups = [
        {'value': group, 'responses': group_counts[group]}
        for group in raw_groups if group_counts[group] < minimum
    ]
    selected_groups = [group for group in groups if group in available_groups]

    def response_ids(group):
        return list(
            dimension.answers.filter(value=group)
            .values_list('response_id', flat=True)
        )

    responses = []
    seen = set()
    answers = question.answers.exclude(value='')
    selected_response_ids = None
    if selected_groups:
        selected_response_ids = {
            item
            for group in selected_groups
            for item in response_ids(group)
        }
        answers = answers.filter(response_id__in=selected_response_ids)
    for answer in answers.select_related('response').order_by('response__display_name'):
        if answer.response_id not in seen:
            responses.append(answer.response)
            seen.add(answer.response_id)
        if len(responses) == 20:
            break
    if selected_groups:
        rows = [
            {
                'survey': survey,
                'label': group,
                'responses': len(response_ids(group)),
                'items': _distribution(
                    question, response_ids=response_ids(group)
                ),
                'metric': _metric(
                    question, response_ids=response_ids(group)
                ),
            }
            for group in selected_groups
        ]
    elif groups:
        rows = []
        responses = []
    else:
        rows = [{
            'survey': survey,
            'label': 'All work areas',
            'responses': survey.response_count,
            'items': _distribution(question),
            'metric': _metric(question),
        }]
        rows = _aligned_rows(rows)
    comparison = None
    if len(rows) > 1:
        highest = max(rows, key=lambda row: row['metric'])
        lowest = min(rows, key=lambda row: row['metric'])
        comparison = {
            'highest': highest,
            'lowest': lowest,
            'gap': highest['metric'] - lowest['metric'],
        }
    return {
        'question': question,
        'surveys': [survey],
        'selected': [],
        'rows': rows,
        'themes': [],
        'employees': responses,
        'distribution_title': 'Response distribution',
        'is_imported': True,
        'dimensions': dimensions,
        'selected_dimension': dimension,
        'groups': available_groups,
        'selected_groups': selected_groups,
        'all_groups_checked': not selected_groups,
        'group_dropdown_open': bool(selected_groups),
        'comparison': comparison,
        'suppressed_groups': suppressed_groups,
        'minimum_group_size': minimum,
    }


def question_detail(question, groups=(), dimension_id='', periods=(), most_recent=False):
    candidates = ImportedQuestion.objects.filter(
        survey_import__name=question.survey_import.name,
        response_type=question.response_type,
    ).select_related('survey_import').order_by('survey_import__financial_year', 'survey_import__quarter')
    compatible = [item for item in candidates if _question_key(item) == _question_key(question)]
    if most_recent:
        selected_questions = compatible[-1:]
    elif periods:
        selected_questions = [item for item in compatible if str(item.survey_import_id) in periods]
    else:
        selected_questions = compatible
    reference = _single_question_detail(question, (), dimension_id)
    selected_dimension = reference['selected_dimension']
    rows, employees, available_groups, suppressed = [], [], [], []
    for item in selected_questions:
        matching_dimension = next((dimension for dimension in item.survey_import.questions.filter(is_dimension=True)
                                   if selected_dimension and _question_key(dimension) == _question_key(selected_dimension)), None)
        data = _single_question_detail(item, groups, str(matching_dimension.pk) if matching_dimension else '')
        # Do not replace a chosen dimension with a different one in another period.
        if selected_dimension and not matching_dimension:
            data['rows'], data['employees'], data['groups'] = [], [], []
        rows.extend(data['rows'])
        employees.extend(data['employees'])
        available_groups.extend(data['groups'])
        suppressed.extend(data['suppressed_groups'])
    changes = add_period_changes(rows)
    available_groups = sorted(set(available_groups))
    reference.update({
        'rows': rows, 'changes': changes, 'surveys': [item.survey_import for item in selected_questions],
        'period_options': [{'slug': str(item.survey_import_id), 'label': item.survey_import.label} for item in compatible],
        'selected': [str(item.survey_import_id) for item in selected_questions],
        'groups': available_groups, 'selected_groups': [group for group in groups if group in available_groups],
        'all_groups_checked': not groups, 'group_dropdown_open': bool(groups),
        'employees': list({item.pk: item for item in employees}.values())[:20],
        'suppressed_groups': suppressed,
        'show_themes': question.response_type == 'written',
        'group_filter_invalid': bool(groups) and not rows,
        'comparison': reference['comparison'] if len(selected_questions) == 1 and not groups else None,
    })
    if len(selected_questions) == 1 and len(rows) > 1:
        highest, lowest = max(rows, key=lambda row: row['metric']), min(rows, key=lambda row: row['metric'])
        reference['comparison'] = {'highest': highest, 'lowest': lowest, 'gap': highest['metric'] - lowest['metric']}
    return reference


def _question_key(question):
    return question.canonical_slug or normalize_question(question.text)


def employee_detail(response, survey_id=''):
    history = list(
        ImportedResponse.objects.filter(
            respondent_key=response.respondent_key,
            survey_import__name=response.survey_import.name,
        )
        .select_related('survey_import')
        .prefetch_related(
            'answers__question',
            'answers__text_annotations__theme',
        )
        .order_by(
            'survey_import__financial_year',
            'survey_import__quarter',
            'row_number',
        )
    )
    selected_candidates = [
        item for item in history
        if survey_id and str(item.survey_import_id) == str(survey_id)
    ]
    selected = next(
        (item for item in selected_candidates if item.pk == response.pk),
        selected_candidates[-1] if selected_candidates else history[-1],
    )
    selected_index = history.index(selected)
    selected_period = (selected.survey_import.financial_year, selected.survey_import.quarter)
    previous_response = next(
        (item for item in reversed(history[:selected_index])
         if (item.survey_import.financial_year, item.survey_import.quarter) < selected_period),
        None,
    )
    previous_answers = {}
    if previous_response:
        previous_answers = {
            _question_key(answer.question): answer.value
            for answer in previous_response.answers.all()
        }

    quantitative = []
    written = []
    detected_themes = {}
    for answer in selected.answers.all():
        previous = previous_answers.get(_question_key(answer.question), '')
        item = {
            'question': answer.question,
            'raw_value': answer.value,
            'answer': answer.value if answer.value.strip() else 'No response',
            'previous': previous if previous.strip() else 'No previous answer',
            'change': answer_change(answer.value, previous, answer.question.response_type),
            'change_summary': answer_change(answer.value, previous, answer.question.response_type, concise=True),
            'previous_survey': (
                previous_response.survey_import if previous_response else None
            ),
        }
        if answer.question.response_type == 'written':
            item['annotations'] = [
                annotation
                for annotation in answer.text_annotations.all()
                if annotation.theme.status == 'reviewed'
            ]
            for annotation in item['annotations']:
                detected_themes[annotation.theme_id] = annotation
            written.append(item)
        else:
            quantitative.append(item)

    averages = []
    for historical_response in history:
        scores = [
            AGREEMENT_SCORES[answer.value.casefold()]
            for answer in historical_response.answers.all()
            if (
                answer.question.response_type == 'agreement'
                and answer.value.casefold() in AGREEMENT_SCORES
            )
        ]
        averages.append({
            'survey': historical_response.survey_import,
            'average': round(sum(scores) / len(scores), 1) if scores else None,
        })

    previous_theme_names = set()
    if previous_response:
        previous_theme_names = set(
            TextAnnotation.objects.filter(
                answer__response=previous_response,
                theme__status='reviewed',
            ).values_list('theme__name', flat=True)
        )
    current_theme_names = {
        annotation.theme.name for annotation in detected_themes.values()
    }

    return {
        'employee': selected,
        'surveys': [item.survey_import for item in history],
        'selected_survey': selected.survey_import,
        'answers': quantitative,
        'written_answers': written,
        'themes': [],
        'history': averages,
        'excerpt': written[0]['answer'] if written else '',
        'is_imported': True,
        'detected_themes': list(detected_themes.values()),
        'new_themes': sorted(current_theme_names - previous_theme_names),
        'themes_no_longer_detected': sorted(
            previous_theme_names - current_theme_names
        ),
    }
