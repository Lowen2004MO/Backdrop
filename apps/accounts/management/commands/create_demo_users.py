import os
from getpass import getpass
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import User
from people_pulse.cloud_secrets import get_secret_string

USERS = [
    ('admin@example.test', 'Demo', 'Administrator', 'People Pulse Administrators'),
    ('analyst@example.test', 'Demo', 'Analyst', 'People Pulse Analysts'),
    ('stakeholder@example.test', 'Demo', 'Stakeholder', 'People Pulse Stakeholders'),
]

class Command(BaseCommand):
    help = 'Create development-only demo groups and users'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Development password (prefer PEOPLE_PULSE_DEMO_PASSWORD)')

    def handle(self, *args, **options):
        password = options['password'] or os.environ.get('PEOPLE_PULSE_DEMO_PASSWORD')
        password_secret_arn = os.environ.get(
            'PEOPLE_PULSE_DEMO_PASSWORD_SECRET_ARN'
        )
        if not password and password_secret_arn:
            password = get_secret_string(password_secret_arn)
        if not password:
            password = getpass('Demo password: ')
        if len(password) < 10:
            raise CommandError('Use a development password of at least 10 characters.')
        upload_permission = Permission.objects.get(codename='add_surveyuploadpermission')
        for username, first, last, group_name in USERS:
            group, _ = Group.objects.get_or_create(name=group_name)
            if group_name != 'People Pulse Stakeholders':
                group.permissions.add(upload_permission)
            user, _ = User.objects.get_or_create(username=username, defaults={'email': username})
            user.first_name, user.last_name = first, last
            user.is_staff = group_name == 'People Pulse Administrators'
            user.is_superuser = user.is_staff
            user.set_password(password)
            user.save()
            user.groups.set([group])
            self.stdout.write(self.style.SUCCESS(f'Ready: {username} ({group_name})'))
