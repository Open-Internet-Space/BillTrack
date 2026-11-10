import datetime as dt
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from estate_app.models import Tenant, Bill, Payment, EmailTemplate, ReminderDelivery, ReminderSettings
from estate_app.reminders.service import send_reminders, preview, smtp_fingerprint

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',EMAIL_HOST_USER='sender@example.invalid',EMAIL_HOST_PASSWORD='test-only',DEFAULT_FROM_EMAIL='Office <sender@example.invalid>')
class SMTPPreviewTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('preview-admin','admin@example.invalid','Synthetic-preview-passphrase-83!')
        self.client.force_login(self.user)
        self.tenant=Tenant.objects.create(name='Example Vendor',type='Shop',email='vendor@example.invalid',penalty_type='none',gst_applicable=False)
        self.bill=Bill.objects.create(tenant=self.tenant,month=1,year=2026,rent=100,issue_date=timezone.localdate()-dt.timedelta(days=20))
        self.template=EmailTemplate.objects.create(name='Preview test',subject='Reminder for {allottee_name}',body='{bill_details}\nTotal: {outstanding_total}')

    def prepared(self):
        from estate_app.reminders.composition import prepare_messages
        return prepare_messages({str(self.tenant.uuid)},self.template,self.user.pk)

    def test_preview_is_editable_and_sends_nothing(self):
        response=self.client.post('/admin/email-reminders/',{'action':'prepare','allottee':[str(self.tenant.uuid)],'template':self.template.pk})
        self.assertContains(response,'Review emails before sending')
        self.assertContains(response,'Confirm and send')
        self.assertContains(response,'vendor@example.invalid')
        self.assertContains(response,'100.00')
        self.assertEqual(ReminderDelivery.objects.count(),0)
        self.assertEqual(len(getattr(mail,'outbox',[])),0)

    def test_only_confirmed_edited_content_is_sent_and_replay_blocked(self):
        data=self.prepared();data[0].update(to='reviewed@example.invalid',cc='authority@example.invalid',subject='Reviewed subject',body='Reviewed exact wording')
        result=send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(result['accepted'],1)
        self.assertEqual(mail.outbox[0].subject,'Reviewed subject')
        self.assertEqual(mail.outbox[0].body,'Reviewed exact wording')
        self.assertEqual(mail.outbox[0].to,['reviewed@example.invalid'])
        self.assertEqual(mail.outbox[0].cc,['authority@example.invalid'])
        self.assertEqual(ReminderDelivery.objects.get().recipient,'reviewed@example.invalid')
        with self.assertRaises(ValidationError):send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(len(mail.outbox),1)

    def test_no_preview_and_automatic_cannot_send(self):
        ReminderSettings.objects.create(automatic_enabled=True,verified_config=smtp_fingerprint())
        for options in [{},{'automatic':True}]:
            self.assertIn('error',send_reminders(**options))
        self.assertEqual(ReminderDelivery.objects.count(),0)
        response=self.client.post('/admin/email-reminders/',{'action':'send','allottee':[str(self.tenant.uuid)]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(ReminderDelivery.objects.count(),0)

    def test_changed_payment_or_recipient_requires_new_preview(self):
        data=self.prepared()
        Payment.objects.create(bill=self.bill,amount=10)
        with self.assertRaises(ValidationError):send_reminders(confirmed=data,user_id=self.user.pk)
        data=self.prepared();self.tenant.email='changed@example.invalid';self.tenant.save()
        with self.assertRaises(ValidationError):send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(ReminderDelivery.objects.count(),0)

    def test_expired_tampered_or_other_user_token_rejected(self):
        data=self.prepared()
        with self.assertRaises(ValidationError):send_reminders(confirmed=data,user_id=self.user.pk+1)
        with patch('estate_app.reminders.composition.signing.loads',side_effect=signing.SignatureExpired('expired')):
            with self.assertRaises(ValidationError):send_reminders(confirmed=data,user_id=self.user.pk)
        data[0]['token']='tampered'
        with self.assertRaises(ValidationError):send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(ReminderDelivery.objects.count(),0)

    def test_invalid_headers_and_sender_are_inline_errors(self):
        data=self.prepared();data[0]['subject']='Bad\r\nBcc: bad@example.invalid'
        with self.assertRaises(ValidationError):send_reminders(confirmed=data,user_id=self.user.pk)
        with override_settings(DEFAULT_FROM_EMAIL='Office, no mailbox'):
            response=self.client.post('/admin/email-reminders/',{'action':'test','address':'test@example.invalid'})
            self.assertContains(response,'DEFAULT_FROM_EMAIL')
        self.assertEqual(ReminderDelivery.objects.count(),0)

    def test_confirm_post_requires_valid_preview_formset(self):
        data=self.prepared()[0]
        payload={'action':'confirm_send','emails-TOTAL_FORMS':'1','emails-INITIAL_FORMS':'0','emails-MIN_NUM_FORMS':'1','emails-MAX_NUM_FORMS':'25',**{'emails-0-'+key:value for key,value in data.items()}}
        response=self.client.post('/admin/email-reminders/',payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(ReminderDelivery.objects.count(),1)

    def test_cli_send_requires_admin_preview_and_automatic_is_noop(self):
        from django.core.management import call_command,CommandError
        from io import StringIO
        with self.assertRaises(CommandError):call_command('send_bill_reminders','--send',stdout=StringIO())
        call_command('send_bill_reminders','--automatic',stdout=StringIO())
        self.assertEqual(ReminderDelivery.objects.count(),0)

    def test_changed_balance_after_claim_is_skipped_without_smtp(self):
        data=self.prepared();original=preview;calls=0
        def changing_preview(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==3:Payment.objects.create(bill=self.bill,amount=10)
            return original(*args,**kwargs)
        with patch('estate_app.reminders.service.preview',side_effect=changing_preview):
            result=send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(result['skipped'],1)
        self.assertEqual(ReminderDelivery.objects.get().status,'skipped')
        self.assertEqual(len(getattr(mail,'outbox',[])),0)

    def test_invalid_confirmation_preserves_edits_and_never_sends(self):
        data=self.prepared()[0];data['to']='invalid'
        payload={'action':'confirm_send','emails-TOTAL_FORMS':'1','emails-INITIAL_FORMS':'0','emails-MIN_NUM_FORMS':'1','emails-MAX_NUM_FORMS':'25',**{'emails-0-'+key:value for key,value in data.items()}}
        response=self.client.post('/admin/email-reminders/',payload)
        self.assertContains(response,'Review emails before sending')
        self.assertContains(response,'100.00')
        self.assertEqual(ReminderDelivery.objects.count(),0)
        self.assertEqual(len(getattr(mail,'outbox',[])),0)

    def test_partial_smtp_recipient_acceptance_requires_review(self):
        from django.core.mail.backends.smtp import EmailBackend
        from unittest.mock import Mock
        data=self.prepared();data[0]['cc']='authority@example.invalid'
        backend=EmailBackend();backend.open=Mock(return_value=False)
        wire=Mock();wire.sendmail.return_value={'vendor@example.invalid':(550,b'private rejection')};backend.connection=wire
        with patch('estate_app.reminders.service.get_connection',return_value=backend):
            result=send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(result['review'],1)
        self.assertEqual(result['accepted'],0)
        self.assertEqual(ReminderDelivery.objects.get().status,'review')
        self.assertEqual(wire.sendmail.call_count,1)
        self.assertNotIn('private rejection',ReminderDelivery.objects.get().error)

    def test_all_smtp_recipients_refused_is_retryable_not_accepted(self):
        from django.core.mail.backends.smtp import EmailBackend
        from smtplib import SMTPRecipientsRefused
        from unittest.mock import Mock
        data=self.prepared();data[0]['cc']='authority@example.invalid'
        backend=EmailBackend();backend.open=Mock(return_value=False)
        wire=Mock();wire.sendmail.side_effect=SMTPRecipientsRefused({'vendor@example.invalid':(550,b'private'), 'authority@example.invalid':(550,b'private')});backend.connection=wire
        with patch('estate_app.reminders.service.get_connection',return_value=backend):result=send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(result['failed'],1)
        self.assertEqual(ReminderDelivery.objects.get().status,'failed')

    def test_full_smtp_acceptance_includes_reviewed_to_and_cc(self):
        from django.core.mail.backends.smtp import EmailBackend
        from unittest.mock import Mock
        data=self.prepared();data[0]['cc']='authority@example.invalid';data[0]['body']='Exact approved body'
        backend=EmailBackend();backend.open=Mock(return_value=False)
        wire=Mock();wire.sendmail.return_value={};backend.connection=wire
        with patch('estate_app.reminders.service.get_connection',return_value=backend):result=send_reminders(confirmed=data,user_id=self.user.pk)
        self.assertEqual(result['accepted'],1)
        self.assertEqual(wire.sendmail.call_args.args[1],['vendor@example.invalid','authority@example.invalid'])
        self.assertIn(b'Exact approved body',wire.sendmail.call_args.args[2])
