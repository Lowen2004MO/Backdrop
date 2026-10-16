from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pulse', '0003_importedquestion_importedresponse_importedanswer_and_more')]

    operations = [
        migrations.AddField(
            model_name='importedresponse',
            name='cohort',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
