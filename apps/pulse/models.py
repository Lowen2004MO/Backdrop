import uuid

from django.conf import settings
from django.db import models

class SurveyUploadPermission(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [('add_surveyuploadpermission', 'Can upload and validate a survey')]


class SurveyImport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    financial_year = models.CharField(max_length=10)
    quarter = models.CharField(max_length=2)
    source_filename = models.CharField(max_length=255)
    response_count = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    exact_duplicates = models.PositiveIntegerField(default=0)
    possible_repeats = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    unmapped_questions = models.PositiveIntegerField(default=0)
    mapping_counts = models.JSONField(default=dict, blank=True)
    version = models.CharField(max_length=20, default='v1.0')
    status = models.CharField(max_length=30, default='Validated')
    text_analysis_version = models.CharField(max_length=40, blank=True)
    text_analysed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_imports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        constraints = [models.UniqueConstraint(fields=('name', 'financial_year', 'quarter'), name='unique_local_survey_import')]

    def __str__(self):
        return f'{self.name} ({self.financial_year} {self.quarter})'

    @property
    def label(self):
        return f'{self.name} - {self.financial_year} {self.quarter}'

    @property
    def responses(self):
        return self.response_count

    @property
    def analysis_status(self):
        return self.status


class ImportedQuestion(models.Model):
    RESPONSE_TYPES = (
        ('agreement', 'Agreement scale'),
        ('rating', 'Rating scale'),
        ('binary', 'Yes / no'),
        ('numeric', 'Number'),
        ('recommendation', 'Recommendation score'),
        ('written', 'Written response'),
        ('choice', 'Choice'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_import = models.ForeignKey(
        SurveyImport,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    source_header = models.TextField()
    text = models.TextField()
    response_type = models.CharField(max_length=20, choices=RESPONSE_TYPES)
    mapping_state = models.CharField(max_length=30)
    canonical_slug = models.SlugField(max_length=100, blank=True)
    position = models.PositiveIntegerField()
    is_dimension = models.BooleanField(default=False)

    class Meta:
        ordering = ('position',)
        constraints = [
            models.UniqueConstraint(
                fields=('survey_import', 'position'),
                name='unique_imported_question_position',
            )
        ]

    @property
    def slug(self):
        return f'uploaded-{self.pk}'

    @property
    def comparable(self):
        return False

    @property
    def movement(self):
        return 0

    @property
    def metric_label(self):
        return {
            'agreement': 'positive',
            'rating': 'positive',
            'binary': 'yes',
            'numeric': 'response rate',
            'recommendation': 'promoter',
            'written': 'response rate',
            'choice': 'largest group',
        }[self.response_type]

    @property
    def latest_positive(self):
        values = list(
            self.answers.exclude(value='').values_list('value', flat=True)
        )
        total = self.survey_import.response_count
        if not total:
            return 0
        normalised = [value.strip().casefold() for value in values]
        if self.response_type == 'agreement':
            count = sum(value in ('agree', 'strongly agree') for value in normalised)
        elif self.response_type == 'rating':
            count = sum(
                value in (
                    'comfortable',
                    'very comfortable',
                    'easy',
                    'very easy',
                )
                for value in normalised
            )
        elif self.response_type == 'binary':
            count = sum(value == 'yes' for value in normalised)
        elif self.response_type == 'recommendation':
            count = 0
            for value in normalised:
                try:
                    count += float(value) >= 9
                except ValueError:
                    continue
        elif self.response_type == 'choice' and normalised:
            from collections import Counter
            count = Counter(normalised).most_common(1)[0][1]
        else:
            count = len(values)
        return round(count * 100 / total)

    def __str__(self):
        return self.text


class ImportedResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_import = models.ForeignKey(
        SurveyImport,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    respondent_key = models.CharField(max_length=64, db_index=True)
    display_name = models.CharField(max_length=255)
    cohort = models.CharField(max_length=255, blank=True)
    row_number = models.PositiveIntegerField()

    class Meta:
        ordering = ('display_name', 'row_number')
        constraints = [
            models.UniqueConstraint(
                fields=('survey_import', 'row_number'),
                name='unique_imported_response_row',
            )
        ]

    @property
    def name(self):
        return self.display_name

    @property
    def role(self):
        return self.cohort or self.survey_import.name

    @property
    def surveys(self):
        return ImportedResponse.objects.filter(
            respondent_key=self.respondent_key
        ).values('survey_import_id').distinct().count()

    @property
    def themes(self):
        return ()

    @property
    def movement(self):
        return 0

    @property
    def indicator(self):
        return 'Uploaded response'

    def __str__(self):
        return f'{self.display_name} - {self.survey_import}'


class ImportedAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.ForeignKey(
        ImportedResponse,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        ImportedQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    value = models.TextField(blank=True)

    class Meta:
        ordering = ('question__position',)
        constraints = [
            models.UniqueConstraint(
                fields=('response', 'question'),
                name='unique_imported_answer',
            )
        ]

    def __str__(self):
        return f'{self.response.display_name}: {self.question.text}'


class TextTheme(models.Model):
    STATUSES = (
        ('reviewed', 'Human reviewed'),
        ('proposed', 'Proposed for review'),
        ('rejected', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_import = models.ForeignKey(
        SurveyImport,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='local_themes',
        help_text='Blank for catalogue themes; set for survey-specific discoveries.',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    keywords = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default='proposed')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_text_themes',
    )

    class Meta:
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(
                fields=('survey_import', 'name'),
                name='unique_survey_text_theme',
            ),
        ]

    def __str__(self):
        return self.name


class TextAnnotation(models.Model):
    SENTIMENTS = (
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('mixed', 'Mixed'),
        ('neutral', 'Neutral'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer = models.ForeignKey(
        ImportedAnswer,
        on_delete=models.CASCADE,
        related_name='text_annotations',
    )
    theme = models.ForeignKey(
        TextTheme,
        on_delete=models.CASCADE,
        related_name='annotations',
    )
    sentiment = models.CharField(max_length=10, choices=SENTIMENTS)
    confidence = models.PositiveSmallIntegerField()
    evidence = models.TextField()
    model_version = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-confidence', 'theme__name')
        constraints = [
            models.UniqueConstraint(
                fields=('answer', 'theme', 'model_version'),
                name='unique_versioned_text_annotation',
            ),
        ]

    def __str__(self):
        return f'{self.theme.name}: {self.answer}'
