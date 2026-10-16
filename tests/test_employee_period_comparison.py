import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.pulse.models import ImportedAnswer, ImportedQuestion, ImportedResponse, SurveyImport


pytestmark = pytest.mark.django_db


@pytest.fixture
def employee_periods(client):
    viewer = User.objects.create_user(username='period-reviewer')
    client.force_login(viewer)
    responses = []
    for quarter, value in [('Q1', 'Disagree'), ('Q2', 'Neutral'), ('Q3', 'Agree')]:
        survey = SurveyImport.objects.create(name='Employee pulse', financial_year='FY2026', quarter=quarter, response_count=1)
        response = ImportedResponse.objects.create(survey_import=survey, respondent_key='one-person', display_name='Test person', row_number=1)
        question = ImportedQuestion.objects.create(survey_import=survey, text='I am happy at IIG', canonical_slug='happy-at-iig', response_type='agreement', position=0)
        ImportedAnswer.objects.create(response=response, question=question, value=value)
        written = ImportedQuestion.objects.create(survey_import=survey, text='What influenced your answers above?', canonical_slug='work-experience-influence', response_type='written', position=1)
        ImportedAnswer.objects.create(response=response, question=written, value=f'{quarter} exact answer\nSecond line.')
        if quarter == 'Q1':
            old_question = ImportedQuestion.objects.create(survey_import=survey, text='Old optional question', response_type='numeric', position=2)
            ImportedAnswer.objects.create(response=response, question=old_question, value='3')
        responses.append(response)
    return responses


def test_employee_compares_only_chosen_periods_in_date_order(client, employee_periods):
    first, middle, latest = employee_periods
    page = client.get(reverse('pulse:employee', args=[latest.pk]), {
        'compare': '1', 'period': [str(latest.survey_import_id), str(first.survey_import_id)],
    })
    assert page.status_code == 200
    assert page.context['comparison_periods'] == [first.survey_import, latest.survey_import]
    agreement = page.context['comparison_answers'][0]
    assert [cell['answer'] for cell in agreement['cells']] == ['Disagree', 'Agree']
    assert agreement['cells'][1]['change_summary'] == '+2 scale points'
    assert 'Q2 exact answer' not in page.content.decode()
    assert 'Q1 exact answer\nSecond line.' in page.content.decode()
    assert 'Q3 exact answer\nSecond line.' in page.content.decode()
    old = next(row for row in page.context['comparison_answers'] if row['question'].text == 'Old optional question')
    assert old['cells'][1]['answer'] == 'Not asked in this period'


def test_employee_all_recent_and_empty_selections(client, employee_periods):
    url = reverse('pulse:employee', args=[employee_periods[-1].pk])
    assert len(client.get(url, {'all_periods': '1'}).context['comparison_periods']) == 3
    recent = client.get(url, {'most_recent': '1'})
    assert len(recent.context['comparison_periods']) == 1
    assert len(recent.context['comparison_answers'][0]['cells']) == 1
    for selection in [{'compare': '1'}, {'period': ['unknown-period']}]:
        page = client.get(url, selection)
        assert page.context['comparison_periods'] == []
        assert b'No periods are selected' in page.content
