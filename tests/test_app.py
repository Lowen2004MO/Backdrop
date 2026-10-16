import uuid
import pytest
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from apps.accounts.models import User
from apps.pulse.models import (
    ImportedAnswer,
    ImportedQuestion,
    ImportedResponse,
    SurveyImport,
    TextAnnotation,
    TextTheme,
)
from services import queries
from services.synthetic_repository import repository
from services.question_mapping import suggest_question_mappings

pytestmark = pytest.mark.django_db

@pytest.fixture
def user():
    return User.objects.create_user(username='viewer@example.test',email='viewer@example.test',password='demo-password-123',first_name='Demo',last_name='Viewer')

@pytest.fixture
def upload_user():
    user=User.objects.create_user(username='analyst@example.test',email='analyst@example.test',password='demo-password-123')
    group=Group.objects.create(name='People Pulse Analysts')
    group.permissions.add(Permission.objects.get(codename='add_surveyuploadpermission'))
    user.groups.add(group)
    return user

def test_protected_routes_redirect_to_login(client):
    for name in ('dashboard','questions','themes','employees','surveys','reports'):
        response=client.get(reverse(f'pulse:{name}'))
        assert response.status_code==302
        assert reverse('accounts:login') in response.url

def test_health_endpoint_checks_database_without_authentication(client):
    response=client.get(reverse('pulse:health'))
    assert response.status_code==200
    assert response.json()=={'status':'ok'}

def test_login_and_post_logout(client,user):
    response=client.post(reverse('accounts:login'),{'username':user.username,'password':'demo-password-123'})
    assert response.status_code==302
    assert client.get(reverse('pulse:dashboard')).status_code==200
    assert client.post(reverse('accounts:logout')).status_code==302
    assert client.get(reverse('pulse:dashboard')).status_code==302

def test_logout_get_not_allowed(client,user):
    client.force_login(user)
    assert client.get(reverse('accounts:logout')).status_code==405

def test_upload_role_access(client,user,upload_user):
    client.force_login(user)
    assert b'header-action' not in client.get(reverse('pulse:dashboard')).content
    response=client.get(reverse('pulse:upload'),raise_request_exception=False)
    assert response.status_code==403
    client.force_login(upload_user)
    assert client.get(reverse('pulse:upload')).status_code==200
    assert b'Upload survey' in client.get(reverse('pulse:dashboard')).content

def test_named_routes_reverse():
    assert reverse('pulse:question',args=['supported-at-work'])=='/questions/supported-at-work/'
    assert reverse('pulse:theme',args=['workload-pressure'])=='/themes/workload-pressure/'
    assert reverse('pulse:employee',args=[repository.employees()[0].id]).startswith('/employees/')
    assert reverse('pulse:survey',args=['fy24-q1'])=='/surveys/fy24-q1/'
    assert reverse('pulse:configure_report')=='/reports/configure/'

def test_navigation_and_active_state(client,user):
    client.force_login(user)
    response=client.get(reverse('pulse:questions'))
    body=response.content.decode()
    for label in ('Dashboard','Questions','Themes','Employees','Surveys','Reports'):
        assert label in body
    assert 'aria-current=\'page\'>Questions' in body

def test_dashboard_multi_period_htmx(client,user):
    client.force_login(user)
    periods=['fy24-q1','fy24-q2','fy25-q4']
    response=client.get(reverse('pulse:dashboard'),{'period':periods},HTTP_HX_REQUEST='true')
    assert response.status_code==200
    assert 'dashboard/_view.html' in [template.name for template in response.templates]
    assert response.context['selected']==periods
    assert b'<html' not in response.content

def test_period_shortcuts_and_dropdown(client,user):
    client.force_login(user)
    response=client.get(reverse('pulse:dashboard'),{'most_recent':'1'},HTTP_HX_REQUEST='true')
    assert response.context['selected']==['fy25-q4']
    response=client.get(reverse('pulse:dashboard'),{'all_periods':'1'},HTTP_HX_REQUEST='true')
    assert len(response.context['selected'])==8
    full=client.get(reverse('pulse:dashboard'))
    assert b'Most recent only' in full.content and b'All periods' in full.content
    assert b'Select survey periods' in full.content and b'period-dropdown-panel' in full.content
    assert b'id=\'most-recent-period\'' in full.content and b'id=\'all-survey-periods\'' in full.content

@pytest.mark.parametrize(('name','arg','text'),[
    ('questions',None,'standard question catalogue'),('question','supported-at-work','Response distribution'),
    ('themes',None,'Model-generated'),('theme','workload-pressure','do not prove causation'),
    ('employees',None,'not performance scores'),('employee',repository.employees()[0].id,'do not prove causation'),
])
def test_core_pages_render(client,user,name,arg,text):
    client.force_login(user)
    url=reverse(f'pulse:{name}',args=[arg] if arg else None)
    response=client.get(url)
    assert response.status_code==200
    assert text in response.content.decode()

def test_employee_search_htmx(client,user):
    client.force_login(user)
    response=client.post(reverse('pulse:employees'),{'search':'Avery'},HTTP_HX_REQUEST='true')
    assert b'Avery North' in response.content and b'Blair Rowan' not in response.content

def test_invalid_identifiers_are_404(client,user):
    client.force_login(user)
    assert client.get(reverse('pulse:question',args=['not-real'])).status_code==404
    assert client.get(reverse('pulse:theme',args=['not-real'])).status_code==404
    assert client.get(reverse('pulse:employee',args=[uuid.uuid4()])).status_code==404

def test_distribution_counts_reconcile():
    data=queries.question_detail('supported-at-work',['fy24-q1','fy25-q4'])
    for row in data['rows']:
        assert sum(item['count'] for item in row['items'])==row['survey'].responses
        assert sum(item['percentage'] for item in row['items'])==100

def test_supplied_question_catalogue_and_response_types():
    assert len(repository.questions())==18
    assert repository.question('happy-at-iig').text=='I am happy at IIG'
    assert repository.question('training-days-used').response_type=='numeric'
    assert repository.question('workplace-suggestions').response_type=='written'

def test_adaptive_question_mapping_states():
    headers=['Email','Please rate your agreement with these statements about your work experience:.I feel supported at work','I feel well supported at work','A completely new pulse prompt']
    states=suggest_question_mappings(headers)
    assert [item.state for item in states]==['Ignored','Confirmed','Needs review','New question']
    changed=suggest_question_mappings(['I feel supported at work'],{'I feel supported at work':'written'})
    assert changed[0].state=='Not comparable'

def test_upload_validation(client,upload_user):
    client.force_login(upload_user)
    good=SimpleUploadedFile('pulse.csv',b'name,q1,q2\nPerson One,4,5\nPerson Two,3,4',content_type='text/csv')
    response=client.post(reverse('pulse:upload'),{'survey_name':'Test','financial_year':'FY2025','quarter':'Q1','csv_file':good},HTTP_HX_REQUEST='true')
    assert response.status_code==200 and b'Import summary' in response.content
    assert SurveyImport.objects.filter(name='Test', financial_year='FY2025', quarter='Q1').count()==1
    assert b'Test' in client.get(reverse('pulse:surveys')).content
    bad=SimpleUploadedFile('pulse.exe',b'no',content_type='application/octet-stream')
    response=client.post(reverse('pulse:upload'),{'survey_name':'Test','financial_year':'FY2025','quarter':'Q1','csv_file':bad})
    assert b'Select a CSV file' in response.content

def test_upload_rejects_oversize(client,upload_user):
    client.force_login(upload_user)
    big=SimpleUploadedFile('pulse.csv',b'x'*(1_048_577),content_type='text/csv')
    response=client.post(reverse('pulse:upload'),{'survey_name':'Test','financial_year':'FY2025','quarter':'Q1','csv_file':big})
    assert b'1 MB or smaller' in response.content

def test_sample_download_and_manual_upload_round_trip(client,upload_user):
    client.force_login(upload_user)
    download=client.get(reverse('pulse:download_sample'))
    content=b''.join(download.streaming_content)
    assert download.status_code==200
    assert 'people-pulse-demo-upload.csv' in download['Content-Disposition']
    assert len(list(__import__('csv').reader(content.decode().splitlines())))==7
    sample=SimpleUploadedFile('people-pulse-demo-upload.csv',content,content_type='text/csv')
    response=client.post(reverse('pulse:upload'),{'survey_name':'Manual demo','financial_year':'FY2025','quarter':'Q4','csv_file':sample},HTTP_HX_REQUEST='true')
    assert response.status_code==200
    assert b'<strong>6</strong>' in response.content
    assert response.content.count(b'Confirmed')>=18
    assert response.content.count(b'Ignored')>=6

def test_revalidating_same_survey_updates_summary(client,upload_user):
    client.force_login(upload_user)
    url=reverse('pulse:upload')
    for body in (b'name,q1\nOne,4', b'name,q1\nOne,4\nTwo,5'):
        upload=SimpleUploadedFile('pulse.csv',body,content_type='text/csv')
        response=client.post(url,{'survey_name':'Repeated','financial_year':'FY2026','quarter':'Q2','csv_file':upload},HTTP_HX_REQUEST='true')
        assert response.status_code==200
    record=SurveyImport.objects.get(name='Repeated')
    assert record.response_count==2
    assert SurveyImport.objects.filter(name='Repeated').count()==1
    assert b'Existing survey data replaced' in response.content

def test_uploaded_survey_removal_is_confirmed_and_permission_controlled(client,user,upload_user):
    record=SurveyImport.objects.create(name='Incorrect upload',financial_year='FY2025',quarter='Q3',source_filename='wrong.csv',created_by=upload_user)
    url=reverse('pulse:delete_survey_import',args=[record.pk])
    client.force_login(user)
    assert client.get(url,raise_request_exception=False).status_code==403
    assert client.post(url,raise_request_exception=False).status_code==403
    client.force_login(upload_user)
    response=client.get(url)
    assert response.status_code==200 and b'This cannot be undone' in response.content
    assert SurveyImport.objects.filter(pk=record.pk).exists()
    response=client.post(url,follow=True)
    assert response.redirect_chain[-1][0]==reverse('pulse:surveys')
    assert not SurveyImport.objects.filter(pk=record.pk).exists()
    assert b'Removed survey, questions and responses' in response.content


def test_additional_csv_columns_become_questions_with_exact_responses(client,upload_user):
    client.force_login(upload_user)
    content=(
        b'Name,I feel supported at work,What would improve your week?,Office location\n'
        b'Alex Morgan,Agree,More time for focused work,London\n'
        b'Jordan Lee,Disagree,Clearer priorities,Bristol\n'
    )
    upload=SimpleUploadedFile('additional-columns.csv',content,content_type='text/csv')
    response=client.post(
        reverse('pulse:upload'),
        {
            'survey_name':'Additional questions',
            'financial_year':'FY2026',
            'quarter':'Q3',
            'csv_file':upload,
        },
        HTTP_HX_REQUEST='true',
    )
    assert response.status_code==200
    survey=SurveyImport.objects.get(name='Additional questions')
    assert survey.status=='Ready'
    assert survey.questions.count()==3
    written=survey.questions.get(text='What would improve your week?')
    assert written.response_type=='written'
    assert list(written.answers.values_list('value',flat=True))==[
        'More time for focused work',
        'Clearer priorities',
    ]

    question_page=client.get(reverse('pulse:question',args=[written.slug]))
    assert question_page.status_code==200
    assert b'Response provided' in question_page.content
    assert b'Alex Morgan' in question_page.content

    employee=survey.responses.get(display_name='Alex Morgan')
    employee_page=client.get(reverse('pulse:employee',args=[employee.pk]))
    assert employee_page.status_code==200
    assert b'Written responses' in employee_page.content
    assert b'More time for focused work' in employee_page.content


@override_settings(PEOPLE_PULSE_MIN_COHORT_SIZE=1)
def test_microsoft_forms_formats_cohorts_nps_and_safe_anonymous_ids(client,upload_user):
    client.force_login(upload_user)
    header=(
        'Id,Email,What is your name?,What is your primary area of work?,'
        'Please rate your agreement with these statements about your work experience: - I am happy at IIG,'
        'What influenced your answers above?,'
        'Before you go how likely are you to recommend IIG as a place to work?\n'
    )
    first=SimpleUploadedFile(
        'forms.csv',
        (
            header
            + '1,,,Defence,Strongly Agree,Helpful colleagues,10\n'
            + '2,person@example.test,Person One,Central Government,Disagree,Changing priorities,6\n'
        ).encode(),
        content_type='text/csv',
    )
    client.post(
        reverse('pulse:upload'),
        {
            'survey_name':'Forms pulse',
            'financial_year':'FY2026',
            'quarter':'Q1',
            'csv_file':first,
        },
    )
    survey=SurveyImport.objects.get(name='Forms pulse',quarter='Q1')
    assert survey.responses.get(row_number=1).cohort=='Defence'
    assert survey.responses.get(row_number=1).role=='Defence'
    agreement=survey.questions.get(canonical_slug='happy-at-iig')
    assert agreement.text=='I am happy at IIG'
    recommendation=survey.questions.get(response_type='recommendation')

    page=client.get(
        reverse('pulse:question',args=[recommendation.slug]),
        {'cohort':'Defence'},
    )
    content=page.content.decode()
    assert 'All groups combined' in content
    assert 'Detractor (0-6)' in content
    assert 'Passive (7-8)' in content
    assert 'Promoter (9-10)' in content
    assert '100% promoter' in content

    comparison=client.get(
        reverse('pulse:question',args=[recommendation.slug]),
        {'cohort':['Defence','Central Government']},
    ).content.decode()
    assert 'Difference between selected groups' in comparison
    assert 'The gap is <strong>100 percentage points</strong>' in comparison
    assert 'Defence (n=1)' in comparison
    assert 'Central Government (n=1)' in comparison

    second=SimpleUploadedFile(
        'forms-next.csv',
        (header + '1,,,Defence,Agree,Still helpful,9\n').encode(),
        content_type='text/csv',
    )
    client.post(
        reverse('pulse:upload'),
        {
            'survey_name':'Forms pulse',
            'financial_year':'FY2026',
            'quarter':'Q2',
            'csv_file':second,
        },
    )
    next_survey=SurveyImport.objects.get(name='Forms pulse',quarter='Q2')
    assert (
        survey.responses.get(row_number=1).respondent_key
        != next_survey.responses.get(row_number=1).respondent_key
    )


def test_local_text_analysis_acquisition_dimension_associations_and_review(client,upload_user):
    client.force_login(upload_user)
    header=(
        'Name,Did you join IIG through an acquisition?,I am happy at IIG,'
        'What influenced your answers above?,'
        'Do you have any suggestions for improving our workplace?\n'
    )
    rows=(
        'Alex,Yes,Disagree,Tool access is difficult,Parking spaces are needed\n'
        'Blair,Yes,Strongly disagree,System permissions are frustrating,Parking spaces are limited\n'
        'Casey,No,Agree,Helpful team and good support,Flexible benefits would help\n'
        'Devon,No,Strongly agree,Excellent colleagues and support,Flexible rewards would help\n'
    )
    response=client.post(
        reverse('pulse:upload'),
        {
            'survey_name':'Acquisition pulse',
            'financial_year':'FY2026',
            'quarter':'Q1',
            'csv_file':SimpleUploadedFile(
                'acquisition.csv',(header+rows).encode(),content_type='text/csv'
            ),
        },
    )
    assert response.status_code==200
    survey=SurveyImport.objects.get(name='Acquisition pulse',quarter='Q1')
    dimension=survey.questions.get(
        text='Did you join IIG through an acquisition?'
    )
    assert dimension.is_dimension
    assert survey.text_analysis_version=='local-hybrid-embedding-v1'
    assert TextAnnotation.objects.filter(
        answer__response__survey_import=survey,
        theme__name='Tools and access',
    ).count()==2
    employee=survey.responses.get(display_name='Alex')
    employee_page=client.get(
        reverse('pulse:employee',args=[employee.pk])
    ).content.decode()
    assert 'Detected themes for this written answer' in employee_page
    assert 'Tools and access' in employee_page
    assert 'Rule score:' in employee_page

    report=client.get(
        reverse('pulse:survey_text_analysis',args=[survey.pk])
    )
    report_text=report.content.decode()
    assert 'Written-response themes' in report_text
    assert 'Links with quantitative answers' in report_text
    assert 'Tools and access' in report_text
    assert '+100 percentage points' in report_text
    assert 'Did you join IIG through an acquisition?' in report_text

    happiness=survey.questions.get(canonical_slug='happy-at-iig')
    comparison=client.get(
        reverse('pulse:question',args=[happiness.slug]),
        {'dimension':str(dimension.pk),'group':['Yes','No']},
    ).content.decode()
    assert 'Difference between selected groups' in comparison
    assert '100 percentage points' in comparison

    proposal=survey.local_themes.get(name='Suggested topic: Parking')
    review=client.post(
        reverse(
            'pulse:review_text_theme',
            args=[survey.pk,proposal.pk,'reviewed'],
        ),
        follow=True,
    )
    assert review.status_code==200
    proposal.refresh_from_db()
    assert proposal.status=='reviewed'
    assert TextAnnotation.objects.filter(
        answer__response__survey_import=survey,
        theme=proposal,
    ).count()==2

    client.post(
        reverse('pulse:toggle_dimension',args=[survey.pk,dimension.pk])
    )
    dimension.refresh_from_db()
    assert not dimension.is_dimension


def test_reimport_replaces_questions_responses_and_answers(client,upload_user):
    client.force_login(upload_user)
    url=reverse('pulse:upload')
    data={'survey_name':'Replace me','financial_year':'FY2026','quarter':'Q4'}
    first=SimpleUploadedFile(
        'first.csv',
        b'Name,Original question\nAlex,First answer',
        content_type='text/csv',
    )
    client.post(url,{**data,'csv_file':first})
    second=SimpleUploadedFile(
        'second.csv',
        b'Name,Replacement question\nAlex,Second answer\nBlair,Third answer',
        content_type='text/csv',
    )
    client.post(url,{**data,'csv_file':second})
    survey=SurveyImport.objects.get(name='Replace me')
    assert list(survey.questions.values_list('text',flat=True))==['Replacement question']
    assert survey.responses.count()==2
    assert ImportedAnswer.objects.filter(response__survey_import=survey).count()==2


def test_percentage_points_are_explained_and_written_answers_are_exact(client,user):
    client.force_login(user)
    dashboard=client.get(reverse('pulse:dashboard')).content.decode()
    assert 'percentage-point change' in dashboard
    assert ' percentage points' in dashboard
    assert '> pp<' not in dashboard
    employee=client.get(
        reverse('pulse:employee',args=[repository.employees()[0].id])
    ).content.decode()
    assert 'Written responses' in employee
    assert 'What influenced your answers above?' in employee
    assert 'Compare periods' in employee and 'Answers by selected survey period' in employee

def test_report_retains_context_and_confirms(client,user):
    client.force_login(user)
    response=client.get(reverse('pulse:configure_report'),{'source':'Question','period':['fy24-q1','fy25-q4']})
    assert b'fy24-q1, fy25-q4' in response.content
    response=client.post(reverse('pulse:configure_report'),{'report_type':'pdf','charts':'on'})
    assert b'Report generation will be implemented' in response.content
