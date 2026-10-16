import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.pulse.models import ImportedAnswer, ImportedQuestion, ImportedResponse, SurveyImport
from services import imported_analytics
from services import queries
from services.synthetic_repository import WORK_AREAS, repository


pytestmark = pytest.mark.django_db


def test_distribution_rounding_keeps_zero_categories_zero_and_bars_nonnegative():
    rows = imported_analytics._percentage_rows([(str(index), 1) for index in range(6)] + [('Missing', 0)], 6)
    assert sum(item['percentage'] for item in rows) == 100
    assert rows[-1]['percentage'] == 0
    for question in repository.questions():
        context = queries.question_detail(question.slug, groups=WORK_AREAS)
        for row in context['rows']:
            assert all(item['count'] >= 0 and item['percentage'] >= 0 for item in row['items'])
            assert sum(item['count'] for item in row['items']) == row['responses']
            assert sum(item['percentage'] for item in row['items']) == 100


@pytest.fixture
def quantitative_surveys():
    questions = []
    for quarter, cni_values in [('Q1', ['Agree', 'Disagree']), ('Q2', ['Agree', 'Agree'])]:
        survey = SurveyImport.objects.create(name='Work pulse', financial_year='FY2026', quarter=quarter, response_count=4)
        area = ImportedQuestion.objects.create(survey_import=survey, text='What is your primary area of work?', canonical_slug='primary-area', response_type='choice', is_dimension=True, position=0)
        question = ImportedQuestion.objects.create(survey_import=survey, text='I am happy at IIG', canonical_slug='happy-at-iig', response_type='agreement', position=1)
        questions.append(question)
        for index, (work_area, value) in enumerate([
            ('Critical National Infrastructure', cni_values[0]),
            ('Critical National Infrastructure', cni_values[1]),
            ('Central Government', 'Disagree'), ('Central Government', 'Disagree'),
        ], 1):
            response = ImportedResponse.objects.create(survey_import=survey, respondent_key=f'person-{index}', display_name=f'Person {index}', row_number=index, cohort=work_area)
            ImportedAnswer.objects.create(response=response, question=area, value=work_area)
            ImportedAnswer.objects.create(response=response, question=question, value=value)
    return questions


def test_uploaded_work_area_bars_and_changes_are_calculated_from_answers(client, quantitative_surveys):
    viewer = User.objects.create_user(username='quantitative-viewer')
    client.force_login(viewer)
    question = quantitative_surveys[-1]
    for url, params in [
        (reverse('pulse:question', args=[question.slug]), {}),
        (reverse('pulse:dashboard'), {'question': question.slug}),
    ]:
        page = client.get(url, {**params, 'group': 'Critical National Infrastructure'})
        assert page.status_code == 200
        rows = page.context['rows']
        assert len(rows) == 2
        assert [row['responses'] for row in rows] == [2, 2]
        assert all(row['label'] == 'Critical National Infrastructure' for row in rows)
        assert all(sum(item['count'] for item in row['items']) == 2 for row in rows)
        changes = page.context['changes']
        agree = next(item for item in changes[0]['items'] if item['category'] == 'Agree')
        assert (agree['previous_percentage'], agree['percentage'], agree['change']) == (50, 100, 50)
        assert b'Associated themes' not in page.content
        assert b'Leading negative theme' not in page.content
        assert b'+50 percentage points' in page.content
        assert len(page.context['employees']) == 4


def test_unavailable_group_does_not_silently_show_everyone(quantitative_surveys):
    context = imported_analytics.question_detail(quantitative_surveys[-1], ['Unknown group'])
    assert context['rows'] == []
    assert context['employees'] == []
    assert context['group_filter_invalid']


def test_uploaded_period_selection_and_no_unmatched_question_comparison(quantitative_surveys):
    question = quantitative_surveys[-1]
    context = imported_analytics.question_detail(question, periods=[str(question.survey_import_id)])
    assert len(context['rows']) == 1
    assert context['changes'] == []
    quantitative_surveys[0].response_type = 'numeric'
    quantitative_surveys[0].save()
    context = imported_analytics.question_detail(question)
    assert len(context['rows']) == 1
    assert context['changes'] == []
