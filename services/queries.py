from dataclasses import replace
from .synthetic_repository import repository, WORK_AREAS
from .response_comparison import answer_change
from .distribution_comparison import add_period_changes

CATEGORY_SETS = {
    'agreement': ('Strongly disagree','Disagree','Neutral','Agree','Strongly agree','Missing / not applicable'),
    'rating': ('Very difficult / uncomfortable','Difficult / uncomfortable','Neutral','Easy / comfortable','Very easy / comfortable','Missing'),
    'binary': ('Yes','No','Unsure','Missing'),
    'written': ('Response provided','No written response','Missing'),
    'numeric': ('0 days','1-2 days','3-5 days','6+ days','Missing'),
    'choice': ('Consulting','Digital delivery','Corporate services','Other','Missing'),
    'multiple_choice': ('Project workload','Unclear options','Approval or access','Other / none','Missing'),
    'recommendation': ('Detractor (0-6)','Passive (7-8)','Promoter (9-10)','Missing'),
}

WRITTEN_RESPONSE_BANK = {
    'work-experience-influence': (
        'Clear priorities and helpful colleagues influenced my answers.',
        'Regular check-ins have helped, although changing priorities can make planning harder.',
        'The team has been supportive while access to some tools could be improved.',
    ),
    'training-barrier-detail': (
        'Busy delivery periods make it difficult to protect learning time.',
        'It is not always clear which course best fits my role.',
        'Some external courses need earlier approval.',
    ),
    'training-support': (
        'Protected learning time agreed during planning would help.',
        'A short list of learning options linked to my role would be useful.',
        'A simpler approval route would make training easier to arrange.',
    ),
    'workplace-suggestions': (
        'Continue sharing priorities clearly across teams.',
        'Create more opportunities for teams to learn from each other.',
        'Keep meetings focused and improve onboarding documentation.',
    ),
}


def _written_response(question, employee, survey, survey_index):
    choices = WRITTEN_RESPONSE_BANK[question.slug]
    return choices[(employee.id.int + survey_index + len(question.slug)) % len(choices)]

def selected_surveys(slugs):
    available = repository.surveys()
    chosen = [s for s in available if s.slug in slugs] if slugs else list(available)
    return chosen or list(available)

def distribution(question, survey, index):
    metric = max(25, min(90, question.latest_positive - (7-index)*question.movement//7))
    missing = 2 + index % 3
    if question.response_type in ('agreement','rating'):
        neutral = min(12 + (index + len(question.slug)) % 7, 100 - metric - missing)
        other = 100 - metric - neutral - missing
        percentages = [other//3, other-other//3, neutral, metric//2, metric-metric//2, missing]
    elif question.response_type == 'binary':
        unsure = min(7 + index % 4, 100 - metric - missing)
        percentages = [metric, 100-metric-unsure-missing, unsure, missing]
    elif question.response_type == 'written':
        percentages = [metric, 100-metric-missing, missing]
    elif question.response_type == 'numeric':
        other = 100-metric-missing
        percentages = [other//3, other-other//3, metric//2, metric-metric//2, missing]
    elif question.response_type in ('choice','multiple_choice'):
        other = 100-metric-missing
        percentages = [metric, other//3, other//3, other-(2*(other//3)), missing]
    else:
        passive = min(16 + index % 5, 100 - metric - missing)
        percentages = [100-metric-passive-missing, passive, metric, missing]
    categories = CATEGORY_SETS[question.response_type]
    exact_counts = [survey.responses * percentage / 100 for percentage in percentages]
    counts = [int(value) for value in exact_counts]
    remainder = survey.responses - sum(counts)
    order = sorted(range(len(counts)), key=lambda index: exact_counts[index] - counts[index], reverse=True)
    for index in order[:remainder]:
        counts[index] += 1
    return {'survey': survey, 'items': [dict(category=c, percentage=p, count=n) for c,p,n in zip(categories, percentages, counts)], 'metric': metric}

def dashboard(slugs=(), question_slug='', theme_slug='', groups=()):
    data = question_detail(question_slug or repository.questions()[0].slug, slugs, groups)
    data['response_total'] = sum(row['responses'] for row in data['rows'])
    return data

def question_detail(slug, slugs=(), groups=()):
    question = repository.question(slug)
    if not question: return None
    surveys = selected_surveys(slugs)
    selected_groups = [group for group in groups if group in WORK_AREAS]
    rows = []
    for survey in surveys:
        index = list(repository.surveys()).index(survey)
        for group in (selected_groups if groups else ['All work areas']):
            if groups:
                group_index = WORK_AREAS.index(group)
                count = survey.responses // len(WORK_AREAS) + (group_index < survey.responses % len(WORK_AREAS))
                group_survey = replace(survey, responses=count)
                group_question = replace(question, latest_positive=question.latest_positive + group_index * 3 - 9)
                row = distribution(group_question, group_survey, index)
            else:
                count = survey.responses
                row = distribution(question, survey, index)
            row.update({'survey': survey, 'responses': count, 'label': group, 'group': group})
            rows.append(row)
    changes = add_period_changes(rows)
    employees = [employee for index, employee in enumerate(repository.employees())
                 if not groups or WORK_AREAS[index % len(WORK_AREAS)] in selected_groups]
    return {
        'question': question, 'surveys': surveys, 'selected': [s.slug for s in surveys],
        'rows': rows, 'changes': changes,
        'themes': repository.themes()[:3] if question.response_type == 'written' else [],
        'show_themes': question.response_type == 'written', 'employees': employees[:20],
        'groups': WORK_AREAS, 'selected_groups': selected_groups,
        'all_groups_checked': not groups, 'group_dropdown_open': bool(groups),
        'distribution_title': 'Response distribution over time',
        'group_filter_invalid': bool(groups) and not selected_groups,
    }

def theme_detail(slug, slugs=()):
    theme = repository.theme(slug)
    if not theme: return None
    surveys = selected_surveys(slugs)
    all_surveys = list(repository.surveys())
    prevalence = [(s, max(4, theme.prevalence - (7-all_surveys.index(s))*theme.movement//7)) for s in surveys]
    employees = [e for e in repository.employees() if theme.name in e.themes][:5]
    excerpts = [{'employee': e, 'text': f'I have noticed {theme.name.lower()} changing as our priorities evolve.', 'confidence': 82-(i*4), 'state': 'Human-confirmed' if i%2 else 'Model-generated'} for i,e in enumerate(employees)]
    return {'theme':theme, 'surveys':surveys, 'selected':[s.slug for s in surveys], 'prevalence':prevalence, 'questions':repository.questions()[:3], 'excerpts':excerpts}

def _demo_selected_answer(question, employee, survey_index, question_index):
    raw = (question_index + employee.id.int + survey_index) % 5
    if question.response_type == 'binary':
        return 'Yes' if raw > 1 else 'No'
    if question.response_type == 'numeric':
        return str(raw + 1)
    if question.response_type == 'recommendation':
        return str(6 + raw)
    if question.response_type == 'rating':
        labels = (
            ('Very difficult', 'Difficult', 'Neutral', 'Easy', 'Very easy')
            if question.slug == 'accessing-training'
            else ('Very uncomfortable', 'Uncomfortable', 'Neutral', 'Comfortable', 'Very comfortable')
        )
        return labels[raw]
    if question.response_type == 'agreement':
        return ('Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly agree')[raw]
    return CATEGORY_SETS[question.response_type][raw % (len(CATEGORY_SETS[question.response_type]) - 1)]


def employee_detail(employee, survey_slug=''):
    surveys = list(repository.surveys())[-employee.surveys:]
    selected = next((s for s in surveys if s.slug == survey_slug), surveys[-1])
    selected_index=surveys.index(selected)
    previous_survey=surveys[selected_index-1] if selected_index else None
    answers=[]
    quantitative = [q for q in repository.questions() if q.response_type != 'written']
    for i,q in enumerate(quantitative):
        answer = _demo_selected_answer(q, employee, selected_index, i)
        previous = _demo_selected_answer(q, employee, selected_index - 1, i) if previous_survey else ''
        answers.append({
            'question':q, 'answer':answer,
            'raw_value':answer,
            'previous':previous or 'No previous answer',
            'change':answer_change(answer, previous, q.response_type),
            'change_summary':answer_change(answer, previous, q.response_type, concise=True),
            'previous_survey':previous_survey,
        })
    themes=[t for t in repository.themes() if t.name in employee.themes]
    history=[{'survey':s,'average':round(2.7 + ((employee.id.int+i)%5)*.35,1)} for i,s in enumerate(surveys)]
    written_answers=[]
    for question in [q for q in repository.questions() if q.response_type == 'written']:
        written_answers.append({
            'question':question,
            'answer':_written_response(question,employee,selected,selected_index),
            'raw_value':_written_response(question,employee,selected,selected_index),
            'previous':(
                _written_response(question,employee,previous_survey,selected_index-1)
                if previous_survey else 'No previous response'
            ),
            'previous_survey':previous_survey,
            'change':'Changed' if previous_survey else 'No previous answer',
        })
    return {
        'employee':employee,
        'surveys':surveys,
        'selected_survey':selected,
        'answers':answers,
        'written_answers':written_answers,
        'themes':themes,
        'history':history,
        'excerpt':written_answers[0]['answer'],
        'is_imported':False,
    }
