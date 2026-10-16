import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.pulse.models import ImportedAnswer, ImportedQuestion, ImportedResponse, SurveyImport
from services import imported_analytics, queries
from services.response_comparison import answer_change
from services.synthetic_repository import repository


@pytest.mark.parametrize(('current', 'previous', 'kind', 'expected'), [
    ('Agree', 'Disagree', 'agreement', 'Disagree → Agree (+2 scale points)'),
    ('Disagree', 'Neutral', 'agreement', 'Neutral → Disagree (-1 scale point)'),
    ('Yes', 'No', 'binary', 'No → Yes'),
    ('Consulting', 'Digital delivery', 'choice', 'Digital delivery → Consulting'),
    ('5', '3', 'numeric', '3 → 5 (+2)'),
    ('7', '9', 'recommendation', '9 → 7 (-2 recommendation points)'),
    (' Agree ', 'agree', 'agreement', 'No change'),
    ('4', '', 'numeric', 'No previous answer'),
    (' ', '4', 'numeric', '4 → No response'),
])
def test_answer_changes_describe_selection_without_inferring_positivity(current, previous, kind, expected):
    assert answer_change(current, previous, kind) == expected


def test_demo_previous_answers_are_the_preceding_periods_selected_answers():
    employee = repository.employees()[0]
    latest = queries.employee_detail(employee)
    earlier = queries.employee_detail(employee, latest['surveys'][-2].slug)
    earlier_answers = {item['question'].slug: item['answer'] for item in earlier['answers']}
    assert all(item['previous'] == earlier_answers[item['question'].slug] for item in latest['answers'])
    first = queries.employee_detail(employee, latest['surveys'][0].slug)
    assert all(item['change'] == 'No previous answer' for item in first['answers'])
    assert all(item['previous_survey'] is None for item in first['answers'])
    agreement = next(item for item in latest['answers'] if item['question'].response_type == 'agreement')
    assert agreement['answer'] in ('Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly agree')


@pytest.mark.django_db
def test_imported_comparison_uses_same_survey_and_an_earlier_period(client):
    def make_response(name, quarter, row_number, value, survey=None):
        survey = survey or SurveyImport.objects.create(
            name=name, financial_year='FY2026', quarter=quarter, response_count=1,
        )
        question, _ = ImportedQuestion.objects.get_or_create(
            survey_import=survey, position=0,
            defaults={'text': 'I am happy at IIG', 'canonical_slug': 'happy-at-iig',
                      'response_type': 'agreement', 'mapping_state': 'Confirmed'},
        )
        response = ImportedResponse.objects.create(
            survey_import=survey, respondent_key='same-person', display_name='Test person', row_number=row_number,
        )
        ImportedAnswer.objects.create(response=response, question=question, value=value)
        return response

    previous = make_response('Pulse', 'Q1', 1, 'Disagree')
    current_first = make_response('Pulse', 'Q2', 1, 'Neutral')
    current = make_response('Pulse', 'Q2', 2, 'Agree', current_first.survey_import)
    make_response('Unrelated survey', 'Q1', 1, 'Strongly agree')
    context = imported_analytics.employee_detail(current, str(current.survey_import_id))
    assert context['answers'][0]['previous'] == 'Disagree'
    assert context['answers'][0]['previous_survey'] == previous.survey_import
    assert context['answers'][0]['change'] == 'Disagree → Agree (+2 scale points)'
    assert all(item.name == 'Pulse' for item in context['surveys'])

    viewer = User.objects.create_user(username='comparison-viewer', password='local-test-password')
    client.force_login(viewer)
    page = client.get(reverse('pulse:employee', args=[current.pk]), {'survey': str(current.survey_import_id)})
    assert page.status_code == 200
    body = page.content.decode()
    assert 'Choices, numbers and changes' in body
    assert '+2 scale points' in body
    assert 'Average agreement answer by survey' not in body
