from pathlib import Path
from django import forms

class UploadForm(forms.Form):
    survey_name = forms.CharField(max_length=100)
    financial_year = forms.ChoiceField(choices=[('FY2025','FY2025'),('FY2026','FY2026')])
    quarter = forms.ChoiceField(choices=[(f'Q{i}',f'Q{i}') for i in range(1,5)])
    csv_file = forms.FileField(help_text='CSV only, maximum 1 MB. The original file is discarded after parsed questions and responses are saved.')

    def clean_csv_file(self):
        upload = self.cleaned_data['csv_file']
        if Path(upload.name).suffix.lower() != '.csv':
            raise forms.ValidationError('Select a CSV file.')
        if upload.size > 1_048_576:
            raise forms.ValidationError('The file must be 1 MB or smaller.')
        if upload.content_type not in ('text/csv','application/csv','application/vnd.ms-excel','text/plain'):
            raise forms.ValidationError('The selected file does not have an accepted CSV content type.')
        return upload

class ReportForm(forms.Form):
    report_type = forms.ChoiceField(choices=[('pdf','PDF analysis report'),('executive','Written executive report'),('csv','CSV metrics'),('excel','Excel data tables')])
    charts = forms.BooleanField(required=False, initial=True)
    interpretation = forms.BooleanField(required=False, initial=True)
    named_responses = forms.BooleanField(required=False)
    methodology = forms.BooleanField(required=False, initial=True)
