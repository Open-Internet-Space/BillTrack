"""Quarantine signup-created users before reverting to a version without approval enforcement."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from rest_framework.authtoken.models import Token

class Command(BaseCommand):
    help = 'Preview signup users to disable before source rollback; --apply disables access without deleting records.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        users = get_user_model().objects.filter(account_access__signup_created=True)
        count = users.count()
        if options['apply']:
            with transaction.atomic():
                users.update(is_active=False)
                Token.objects.filter(user__in=users).delete()
            self.stdout.write(f'Disabled {count} signup-created account(s) and revoked their tokens. Records retained.')
        else:
            self.stdout.write(f'Preview: {count} signup-created account(s) would be disabled. No changes made.')
