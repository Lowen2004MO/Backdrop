import csv
import io
from functools import wraps
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .forms import ReportForm, UploadForm
from .models import ImportedQuestion, ImportedResponse, SurveyImport, TextTheme
from services.synthetic_repository import repository
from services import queries
from services.csv_import import persist_csv_import
from services import imported_analytics
from services.employee_comparison import employee_comparison
from services.text_analysis import analyse_survey, survey_text_summary

def _periods(request):
    available=list(repository.surveys())
    if request.GET.get('most_recent') == '1': return [available[-1].slug]
    if request.GET.get('all_periods') == '1': return [item.slug for item in available]
    return request.GET.getlist('period')

def _period_context(request, selected):
    most_recent=request.GET.get('most_recent') == '1'
    all_periods=request.GET.get('all_periods') == '1' or not request.GET
    return {'most_recent_checked':most_recent,'all_periods_checked':all_periods,
            'period_dropdown_open':bool(request.GET) and not most_recent and not all_periods}
def _fragment(request, full, fragment): return fragment if request.headers.get('HX-Request') == 'true' else full

def upload_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.has_perm('pulse.add_surveyuploadpermission'):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped

@login_required
def home(request): return redirect('pulse:dashboard')

def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()
    return JsonResponse({'status': 'ok'})

@login_required
def dashboard(request):
    question_slug = request.GET.get('question', '')
    groups = [] if request.GET.get('all_groups') == '1' else request.GET.getlist('group')
    if question_slug.startswith('uploaded-'):
        question_item = get_object_or_404(ImportedQuestion.objects.select_related('survey_import'), pk=question_slug.removeprefix('uploaded-'))
        data = imported_analytics.question_detail(
            question_item, groups, request.GET.get('dimension', ''),
            () if request.GET.get('all_periods') == '1' else request.GET.getlist('period'),
            request.GET.get('most_recent') == '1',
        )
        data['response_total'] = sum(row['responses'] for row in data['rows'])
    else:
        data = queries.dashboard(_periods(request), question_slug, groups=groups)
    data.update({
        'all_surveys': data.get('period_options', repository.surveys()),
        'questions': list(repository.questions()) + list(ImportedQuestion.objects.select_related('survey_import').order_by('-survey_import__financial_year', '-survey_import__quarter', 'position')),
    })
    data.update(_period_context(request,data['selected']))
    return render(request, _fragment(request,'dashboard/index.html','dashboard/_view.html'), data)

@login_required
def questions(request):
    items=list(repository.questions())
    items.extend(
        ImportedQuestion.objects.select_related('survey_import').order_by(
            '-survey_import__updated_at', 'position'
        )
    )
    mode=request.GET.get('filter','all')
    if mode=='improving': items=[q for q in items if q.movement>0]
    if mode=='declining': items=[q for q in items if q.movement<0]
    if request.GET.get('sort')=='name': items.sort(key=lambda q:q.text)
    return render(request,'questions/index.html',{'questions':items,'mode':mode})

@login_required
def question(request, slug):
    groups = [] if request.GET.get('all_groups') == '1' else request.GET.getlist('group') or request.GET.getlist('cohort')
    data=queries.question_detail(slug,_periods(request),groups)
    if not data and slug.startswith('uploaded-'):
        item=get_object_or_404(
            ImportedQuestion.objects.select_related('survey_import'),
            pk=slug.removeprefix('uploaded-'),
        )
        data=imported_analytics.question_detail(
            item, groups, request.GET.get('dimension', ''),
            () if request.GET.get('all_periods') == '1' else request.GET.getlist('period'),
            request.GET.get('most_recent') == '1',
        )
    if not data: raise Http404('Question not found')
    data['all_surveys']=data.get('period_options', repository.surveys())
    data.update(_period_context(request,data['selected']))
    return render(request,_fragment(request,'questions/detail.html','questions/_distribution.html'),data)

@login_required
def themes(request):
    mode=request.GET.get('filter','all')
    items=[t for t in repository.themes() if mode=='all' or t.trend==mode]
    return render(request,'themes/index.html',{'themes':items,'mode':mode})

@login_required
def theme(request, slug):
    data=queries.theme_detail(slug,_periods(request))
    if not data: raise Http404('Theme not found')
    data['all_surveys']=repository.surveys()
    data.update(_period_context(request,data['selected']))
    return render(request,_fragment(request,'themes/detail.html','themes/_results.html'),data)

@login_required
def employees(request):
    params=request.POST if request.method=='POST' else request.GET
    items=list(repository.employees())
    items.extend(
        ImportedResponse.objects.select_related('survey_import').order_by(
            'display_name'
        )
    )
    search=params.get('search','').strip().lower(); mode=params.get('filter','all')
    if search: items=[e for e in items if search in e.name.lower()]
    if mode=='concern': items=[e for e in items if e.movement<0]
    if mode=='improvement': items=[e for e in items if e.movement>0]
    if mode not in ('all','concern','improvement'): items=[e for e in items if mode in [t.lower().replace(' ','-') for t in e.themes]]
    return render(request,_fragment(request,'employees/index.html','employees/_results.html'),{'employees':items,'search':search,'mode':mode,'themes':repository.themes()})

@login_required
def employee(request, employee_id):
    item=repository.employee(employee_id)
    if item:
        data=queries.employee_detail(item,request.GET.get('survey',''))
        load_period = lambda period: queries.employee_detail(item, period)
    else:
        item=get_object_or_404(
            ImportedResponse.objects.select_related('survey_import'),
            pk=employee_id,
        )
        data=imported_analytics.employee_detail(
            item, request.GET.get('survey', '')
        )
        load_period = lambda period: imported_analytics.employee_detail(item, period)
    data = employee_comparison(
        data, load_period, periods=request.GET.getlist('period'),
        most_recent=request.GET.get('most_recent') == '1',
        all_periods=request.GET.get('all_periods') == '1',
        explicit=request.GET.get('compare') == '1',
    )
    return render(request,'employees/detail.html',data)

@login_required
def surveys(request):
    return render(request, 'surveys/index.html', {
        'surveys': repository.surveys(),
        'uploaded_surveys': SurveyImport.objects.select_related(
            'created_by'
        ).prefetch_related('questions'),
    })

@login_required
def survey(request, slug):
    item=next((s for s in repository.surveys() if s.slug==slug),None)
    if not item: raise Http404('Survey not found')
    return render(request,'surveys/detail.html',{'survey':item,'questions':repository.questions()})


@login_required
def imported_survey(request, pk):
    item=get_object_or_404(
        SurveyImport.objects.prefetch_related('questions'),
        pk=pk,
    )
    return render(
        request,
        'surveys/detail.html',
        {'survey':item,'questions':item.questions.all(),'is_imported':True},
    )


@login_required
def survey_text_analysis(request, pk):
    item=get_object_or_404(SurveyImport, pk=pk)
    context={'survey':item}
    context.update(survey_text_summary(item))
    return render(request,'surveys/text_analysis.html',context)


@upload_required
def run_text_analysis(request, pk):
    item=get_object_or_404(SurveyImport, pk=pk)
    if request.method == 'POST':
        count=analyse_survey(item)
        messages.success(request,f'Text analysis refreshed with {count} evidence-based theme annotations.')
    return redirect('pulse:survey_text_analysis',pk=item.pk)


@upload_required
def toggle_dimension(request, pk, question_pk):
    item=get_object_or_404(SurveyImport, pk=pk)
    question=get_object_or_404(item.questions, pk=question_pk)
    if request.method == 'POST':
        if question.response_type not in ('choice','binary'):
            messages.error(request,'Only choice and yes/no questions can be respondent filters.')
        else:
            question.is_dimension=not question.is_dimension
            question.save(update_fields=('is_dimension',))
            state='available as a filter' if question.is_dimension else 'an analytical question only'
            messages.success(request,f'{question.text} is now {state}.')
    return redirect('pulse:imported_survey',pk=item.pk)


@upload_required
def review_text_theme(request, pk, theme_pk, decision):
    item=get_object_or_404(SurveyImport, pk=pk)
    theme=get_object_or_404(TextTheme, pk=theme_pk, survey_import=item)
    if request.method == 'POST' and decision in ('reviewed','rejected'):
        theme.status=decision
        theme.reviewed_by=request.user
        from django.utils import timezone
        theme.reviewed_at=timezone.now()
        theme.save(update_fields=('status','reviewed_by','reviewed_at'))
        if decision == 'reviewed':
            analyse_survey(item)
        messages.success(request,f'{theme.name} marked as {theme.get_status_display().lower()}.')
    return redirect('pulse:survey_text_analysis',pk=item.pk)

@upload_required
def download_sample(request):
    path=settings.BASE_DIR / 'samples' / 'people-pulse-demo-upload.csv'
    return FileResponse(path.open('rb'),as_attachment=True,filename='people-pulse-demo-upload.csv',content_type='text/csv')


@upload_required
def download_acquisition_sample(request):
    path=settings.BASE_DIR / 'samples' / 'people-pulse-acquisition-demo.csv'
    return FileResponse(path.open('rb'),as_attachment=True,filename='people-pulse-acquisition-demo.csv',content_type='text/csv')

@upload_required
def upload(request):
    preview=None
    if request.method=='POST':
        form=UploadForm(request.POST,request.FILES)
        if form.is_valid():
            raw=form.cleaned_data['csv_file'].read()
            try:
                text=raw.decode('utf-8-sig')
                rows=list(csv.reader(io.StringIO(text)))
                if not rows: raise ValueError
                headers=rows[0]
                if (
                    not headers
                    or not any(header.strip() for header in headers)
                    or len(headers) > 100
                    or any(len(header) > 1000 for header in headers)
                ):
                    raise ValueError
                result=persist_csv_import(
                    cleaned_data=form.cleaned_data,
                    filename=Path(form.cleaned_data['csv_file'].name).name,
                    headers=headers,
                    rows=rows[1:],
                    user=request.user,
                )
                configured_by_position={
                    item.position:item
                    for item in result.saved_import.questions.all()
                }
                preview={
                    'total':result.total,
                    'valid':result.valid,
                    'duplicates':result.duplicates,
                    'repeated':result.repeated,
                    'invalid':result.invalid,
                    'unmapped':result.unmapped,
                    'mappings':result.mappings,
                    'mapping_rows':[
                        {
                            'suggestion':suggestion,
                            'question':configured_by_position.get(position),
                        }
                        for position,suggestion in enumerate(result.mappings)
                    ],
                    'saved_import':result.saved_import,
                    'created':result.created,
                }
            except (UnicodeDecodeError,csv.Error,ValueError):
                form.add_error('csv_file','The file could not be read as a UTF-8 CSV with a header row.')
    else: form=UploadForm()
    return render(request,_fragment(request,'surveys/upload.html','surveys/_preview.html'),{'form':form,'preview':preview})

@upload_required
def delete_survey_import(request, pk):
    survey_import = get_object_or_404(SurveyImport, pk=pk)
    if request.method == 'POST':
        label = str(survey_import)
        survey_import.delete()
        messages.success(request, f'Removed survey, questions and responses: {label}.')
        return redirect('pulse:surveys')
    return render(request, 'surveys/delete_confirm.html', {'survey_import': survey_import})

@login_required
def reports(request):
    records=[{'name':'Quarterly leadership overview','type':'PDF','status':'Completed','date':'18 Mar 2025'},{'name':'Workload theme analysis','type':'Excel','status':'Pending','date':'20 Mar 2025'},{'name':'Executive narrative','type':'Written report','status':'Failed','date':'21 Mar 2025'}]
    return render(request,'reports/index.html',{'records':records})

@login_required
def configure_report(request):
    initial={'report_type':request.GET.get('type','pdf'),'named_responses':request.GET.get('employee','') != ''}
    form=ReportForm(request.POST or None,initial=initial)
    confirmed=False
    if request.method=='POST' and form.is_valid():
        confirmed=True
        messages.info(request,'Report generation will be implemented in a later increment.')
    context={'form':form,'confirmed':confirmed,'source':request.GET.get('source','Dashboard'),'periods':request.GET.getlist('period'),'context_query':request.GET.urlencode()}
    return render(request,'reports/configure.html',context)

def error_403(request,exception=None): return render(request,'errors/403.html',status=403)
def error_404(request,exception=None): return render(request,'errors/404.html',status=404)
def error_500(request): return render(request,'errors/500.html',status=500)
