from django.contrib import admin

from .models import (
    ImportedAnswer,
    ImportedQuestion,
    ImportedResponse,
    SurveyImport,
    TextAnnotation,
    TextTheme,
)


class ImportedQuestionInline(admin.TabularInline):
    model = ImportedQuestion
    extra = 0
    readonly_fields = (
        'text',
        'response_type',
        'mapping_state',
        'canonical_slug',
        'position',
    )
    fields = readonly_fields + ('is_dimension',)


class ImportedResponseInline(admin.TabularInline):
    model = ImportedResponse
    extra = 0
    fields = ('display_name', 'cohort', 'row_number')
    readonly_fields = fields


@admin.register(SurveyImport)
class SurveyImportAdmin(admin.ModelAdmin):
    list_display = ('name', 'financial_year', 'quarter', 'response_count', 'status', 'updated_at')
    list_filter = ('financial_year', 'quarter', 'status')
    search_fields = ('name', 'source_filename')
    readonly_fields = ('created_at', 'updated_at')
    inlines = (ImportedQuestionInline, ImportedResponseInline)


@admin.register(ImportedAnswer)
class ImportedAnswerAdmin(admin.ModelAdmin):
    list_display = ('response', 'question')
    list_select_related = ('response', 'question')
    search_fields = ('response__display_name', 'question__text', 'value')


@admin.register(TextTheme)
class TextThemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'survey_import', 'status', 'reviewed_by', 'reviewed_at')
    list_filter = ('status',)
    search_fields = ('name', 'description')


@admin.register(TextAnnotation)
class TextAnnotationAdmin(admin.ModelAdmin):
    list_display = ('theme', 'answer', 'sentiment', 'confidence', 'model_version')
    list_filter = ('sentiment', 'model_version')
    search_fields = ('theme__name', 'evidence')
