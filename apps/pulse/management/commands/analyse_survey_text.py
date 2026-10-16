from django.core.management.base import BaseCommand, CommandError

from apps.pulse.models import SurveyImport
from services.text_analysis import analyse_survey


class Command(BaseCommand):
    help = 'Run the local explainable text-analysis pipeline for imported surveys.'

    def add_arguments(self, parser):
        parser.add_argument('survey', help='Survey UUID or all.')

    def handle(self, *args, **options):
        value = options['survey']
        surveys = SurveyImport.objects.all() if value == 'all' else SurveyImport.objects.filter(pk=value)
        if not surveys.exists():
            raise CommandError('No matching imported survey was found.')
        for survey in surveys:
            count = analyse_survey(survey)
            self.stdout.write(self.style.SUCCESS(
                f'{survey.label}: saved {count} reviewed-theme annotations.'
            ))
