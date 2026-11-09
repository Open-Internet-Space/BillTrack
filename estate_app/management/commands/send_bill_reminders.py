from django.core.management.base import BaseCommand, CommandError
from estate_app.reminders.service import preview, send_reminders

class Command(BaseCommand):
    help='Preview reminders by default; --automatic honours the disabled-by-default administrator switch.'
    def add_arguments(self,parser):
        group=parser.add_mutually_exclusive_group()
        group.add_argument('--send',action='store_true',help='Explicitly send eligible reminders now')
        group.add_argument('--automatic',action='store_true',help='Run only if automatic sending is enabled and verified')
    def handle(self,*args,**options):
        if options['send'] or options['automatic']:
            result=send_reminders(automatic=options['automatic'])
            if result.get('error'):
                raise CommandError(result['error'])
            self.stdout.write(str(result))
            if result['failed'] or result['review']:
                raise CommandError('Some submissions failed or need review. Check Email reminder history before retrying.')
        else:
            groups,skipped=preview()
            self.stdout.write(f'Preview only: {len(groups)} allottee email(s); {sum(len(g["items"]) for g in groups)} bill(s). No mail sent.')
            self.stdout.write(str(skipped))
