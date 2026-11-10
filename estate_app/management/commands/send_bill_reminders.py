from django.core.management.base import BaseCommand, CommandError
from estate_app.reminders.service import preview, send_reminders

class Command(BaseCommand):
    help='Preview eligible reminders; SMTP sending requires confirmation in Admin.'
    def add_arguments(self,parser):
        group=parser.add_mutually_exclusive_group()
        group.add_argument('--send',action='store_true',help='Disabled: use the editable Admin preview')
        group.add_argument('--automatic',action='store_true',help='Compatibility no-op; automatic sending is disabled')
    def handle(self,*args,**options):
        if options['send']:
            raise CommandError('Open Admin Email reminders to preview, edit and confirm each email. Direct sending is disabled.')
        elif options['automatic']:
            self.stdout.write('No mail sent. Automatic reminders are disabled; preview and confirm emails in Admin.')
        else:
            groups,skipped=preview()
            self.stdout.write(f'Preview only: {len(groups)} allottee email(s); {sum(len(g["items"]) for g in groups)} bill(s). No mail sent.')
            self.stdout.write(str(skipped))
