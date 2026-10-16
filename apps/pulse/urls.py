from django.urls import path

from . import views


app_name = 'pulse'
urlpatterns = [
    path('health/', views.health, name='health'),
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('questions/', views.questions, name='questions'),
    path('questions/<slug:slug>/', views.question, name='question'),
    path('themes/', views.themes, name='themes'),
    path('themes/<slug:slug>/', views.theme, name='theme'),
    path('employees/', views.employees, name='employees'),
    path('employees/<uuid:employee_id>/', views.employee, name='employee'),
    path('surveys/', views.surveys, name='surveys'),
    path('surveys/upload/', views.upload, name='upload'),
    path('surveys/sample.csv', views.download_sample, name='download_sample'),
    path('surveys/acquisition-sample.csv', views.download_acquisition_sample, name='download_acquisition_sample'),
    path('surveys/imports/<uuid:pk>/', views.imported_survey, name='imported_survey'),
    path('surveys/imports/<uuid:pk>/text-analysis/', views.survey_text_analysis, name='survey_text_analysis'),
    path('surveys/imports/<uuid:pk>/analyse/', views.run_text_analysis, name='run_text_analysis'),
    path('surveys/imports/<uuid:pk>/dimensions/<uuid:question_pk>/', views.toggle_dimension, name='toggle_dimension'),
    path('surveys/imports/<uuid:pk>/themes/<uuid:theme_pk>/<str:decision>/', views.review_text_theme, name='review_text_theme'),
    path('surveys/imports/<uuid:pk>/delete/', views.delete_survey_import, name='delete_survey_import'),
    path('surveys/<slug:slug>/', views.survey, name='survey'),
    path('reports/', views.reports, name='reports'),
    path('reports/configure/', views.configure_report, name='configure_report'),
]
