from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name='SurveyUploadPermission', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False))], options={'managed': False, 'default_permissions': (), 'permissions': [('add_surveyuploadpermission', 'Can upload and validate a survey')]})]
