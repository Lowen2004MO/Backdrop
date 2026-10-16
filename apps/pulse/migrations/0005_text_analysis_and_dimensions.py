from django.db import migrations, models
import django.db.models.deletion


def mark_existing_work_area_dimensions(apps, schema_editor):
    ImportedQuestion = apps.get_model('pulse', 'ImportedQuestion')
    ImportedQuestion.objects.filter(canonical_slug='primary-area').update(
        is_dimension=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_alter_user_options_alter_user_date_joined_and_more'),
        ('pulse', '0004_importedresponse_cohort'),
    ]

    operations = [
        migrations.AddField(
            model_name='surveyimport',
            name='text_analysis_version',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='surveyimport',
            name='text_analysed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='importedquestion',
            name='is_dimension',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='TextTheme',
            fields=[
                ('id', models.UUIDField(default=__import__('uuid').uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('keywords', models.JSONField(blank=True, default=list)),
                ('status', models.CharField(choices=[('reviewed', 'Human reviewed'), ('proposed', 'Proposed for review'), ('rejected', 'Rejected')], default='proposed', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_text_themes', to='accounts.user')),
                ('survey_import', models.ForeignKey(blank=True, help_text='Blank for catalogue themes; set for survey-specific discoveries.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='local_themes', to='pulse.surveyimport')),
            ],
            options={'ordering': ('name',)},
        ),
        migrations.CreateModel(
            name='TextAnnotation',
            fields=[
                ('id', models.UUIDField(default=__import__('uuid').uuid4, editable=False, primary_key=True, serialize=False)),
                ('sentiment', models.CharField(choices=[('positive', 'Positive'), ('negative', 'Negative'), ('mixed', 'Mixed'), ('neutral', 'Neutral')], max_length=10)),
                ('confidence', models.PositiveSmallIntegerField()),
                ('evidence', models.TextField()),
                ('model_version', models.CharField(max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('answer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='text_annotations', to='pulse.importedanswer')),
                ('theme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to='pulse.texttheme')),
            ],
            options={'ordering': ('-confidence', 'theme__name')},
        ),
        migrations.AddConstraint(
            model_name='texttheme',
            constraint=models.UniqueConstraint(fields=('survey_import', 'name'), name='unique_survey_text_theme'),
        ),
        migrations.AddConstraint(
            model_name='textannotation',
            constraint=models.UniqueConstraint(fields=('answer', 'theme', 'model_version'), name='unique_versioned_text_annotation'),
        ),
        migrations.RunPython(mark_existing_work_area_dimensions, migrations.RunPython.noop),
    ]
