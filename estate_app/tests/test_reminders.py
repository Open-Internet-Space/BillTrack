import datetime as dt
from unittest.mock import patch
from smtplib import SMTPAuthenticationError, SMTPServerDisconnected
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from estate_app.models import Bill, Tenant, Payment
from estate_app.models.reminders import ReminderSettings, ReminderDelivery
from estate_app.reminders.service import cutoff_date, milestone, preview, send_reminders, send_test, smtp_fingerprint

@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
 EMAIL_HOST='smtp.gmail.com',EMAIL_PORT=587,EMAIL_USE_TLS=True,
 EMAIL_HOST_USER='sender@example.invalid',EMAIL_HOST_PASSWORD='test-only',
 DEFAULT_FROM_EMAIL='sender@example.invalid')
class ReminderTests(TestCase):
 def setUp(self):
  self.today=timezone.localdate()
  self.tenant=Tenant.objects.create(name='Reminder test',type='Shop',email='tenant@example.invalid',penalty_type='none',gst_applicable=False)
  self.bill=Bill.objects.create(tenant=self.tenant,month=1,year=2026,rent=100,issue_date=self.today-dt.timedelta(days=20))
 def test_schedule_and_calendar_cutoff(self):
  receipt=dt.date(2026,11,9);due=dt.date(2026,11,14)
  self.assertEqual(cutoff_date(dt.date(2026,11,30)),dt.date(2027,2,28))
  self.assertEqual(cutoff_date(receipt),dt.date(2027,2,9))
  self.assertEqual(cutoff_date(dt.date(2023,11,30)),dt.date(2024,2,29))
  self.assertEqual(cutoff_date(dt.date(2026,1,31)),dt.date(2026,4,30))
  for offset in [-1,0,1,7,14,26,41,56,71,86]:
   self.assertEqual(milestone(receipt,due,due+dt.timedelta(days=offset))[0],offset)
  self.assertIsNone(milestone(receipt,due,dt.date(2027,2,10)))
  self.assertIsNone(milestone(receipt,due,due-dt.timedelta(days=2)))
 def test_preview_is_read_only_and_selects_latest_missed_stage(self):
  groups,skipped=preview(self.today)
  self.assertEqual(len(groups),1);self.assertEqual(groups[0]['items'][0]['offset'],14)
  self.assertEqual(ReminderDelivery.objects.count(),0)
 def test_combines_bills_and_repeated_send_is_suppressed(self):
  Bill.objects.create(tenant=self.tenant,month=2,year=2026,rent=80,issue_date=self.today-dt.timedelta(days=6))
  self.assertEqual(send_reminders(today=self.today)['accepted'],1)
  self.assertEqual(len(mail.outbox),1);self.assertEqual(len(ReminderDelivery.objects.get().items),2)
  self.assertIn('100.00',mail.outbox[0].body)
  self.assertEqual(send_reminders(today=self.today)['accepted'],0)
  self.assertEqual(send_reminders(today=self.today+dt.timedelta(days=1))['accepted'],0)
 def test_paid_bill_stops_sending(self):
  Payment.objects.create(bill=self.bill,amount=100,payment_date=self.today)
  self.assertEqual(preview(self.today)[0],[])
 def test_partial_payment_uses_remaining_balance(self):
  Payment.objects.create(bill=self.bill,amount=30,payment_date=self.today)
  self.assertEqual(preview(self.today)[0][0]['items'][0]['principal'],'70.00')
 def test_pending_receipt_invalid_email_inactive_and_cutoff_are_skipped(self):
  self.bill.issue_date=None;self.bill.save()
  self.assertEqual(preview(self.today)[0],[])
  self.bill.issue_date=self.today-dt.timedelta(days=20);self.bill.save()
  for values in [{'email':''},{'email':'invalid'},{'email':'tenant@example.invalid','active':False}]:
   Tenant.objects.filter(pk=self.tenant.pk).update(**values)
   self.assertEqual(preview(self.today)[0],[])
  Tenant.objects.filter(pk=self.tenant.pk).update(active=True,email='tenant@example.invalid')
  self.assertEqual(preview(self.today+dt.timedelta(days=100))[0],[])
 def test_rechecks_payment_after_preview(self):
  preview(self.today)
  Payment.objects.create(bill=self.bill,amount=100,payment_date=self.today)
  self.assertEqual(send_reminders(today=self.today)['accepted'],0)
 def test_automatic_is_off_by_default(self):
  self.assertEqual(send_reminders(today=self.today,automatic=True)['accepted'],0)
  self.assertEqual(ReminderDelivery.objects.count(),0)
 def test_automatic_requires_verified_current_configuration(self):
  ReminderSettings.objects.create(automatic_enabled=True)
  self.assertEqual(send_reminders(today=self.today,automatic=True)['accepted'],0)
  config=ReminderSettings.objects.get();config.verified_config=smtp_fingerprint();config.save()
  self.assertEqual(send_reminders(today=self.today,automatic=True)['accepted'],1)
 def test_definite_connection_failure_is_retryable(self):
  with patch('estate_app.reminders.service.get_connection') as connection:
   connection.return_value.open.side_effect=SMTPAuthenticationError(535,b'private mail server response')
   self.assertEqual(send_reminders(today=self.today)['failed'],1)
  log=ReminderDelivery.objects.get();self.assertEqual(log.status,'failed')
  self.assertNotIn('private',log.error)
  self.assertEqual(send_reminders(today=self.today)['accepted'],1)
  self.assertEqual(ReminderDelivery.objects.get().attempts,2)
 def test_uncertain_submission_is_not_retried(self):
  with patch('estate_app.reminders.service.EmailMessage.send',side_effect=SMTPServerDisconnected('private detail')):
   self.assertEqual(send_reminders(today=self.today)['review'],1)
  self.assertEqual(ReminderDelivery.objects.get().status,'review')
  self.assertEqual(send_reminders(today=self.today+dt.timedelta(days=1))['accepted'],0)
 def test_interrupted_claim_blocks_duplicate(self):
  group=preview(self.today)[0][0]
  ReminderDelivery.objects.create(allottee_uuid=self.tenant.uuid,allottee=self.tenant,allottee_name=self.tenant.name,send_date=self.today,recipient=self.tenant.email,status='sending',items=group['items'])
  self.assertEqual(send_reminders(today=self.today)['accepted'],0)
  self.assertEqual(send_reminders(today=self.today+dt.timedelta(days=1))['accepted'],0)
 def test_test_message_verifies_configuration_without_billing_history(self):
  send_test('office@example.invalid')
  self.assertEqual(ReminderSettings.objects.get().verified_config,smtp_fingerprint())
  self.assertEqual(ReminderDelivery.objects.count(),0)
  self.assertNotIn(self.bill.invoice_no,mail.outbox[0].body)
 def test_admin_access_and_post_protection(self):
  user=User.objects.create_user('reminder-staff',is_staff=True)
  self.client.force_login(user)
  self.assertEqual(self.client.get('/admin/email-reminders/').status_code,403)
  user.is_superuser=True;user.save();self.client.force_login(user)
  self.assertContains(self.client.get('/admin/email-reminders/'),'Email reminders')
  self.assertEqual(self.client.get('/admin/email-reminders/?action=send').status_code,200)
  self.assertEqual(ReminderDelivery.objects.count(),0)
  self.assertEqual(ReminderSettings.objects.count(),0)
 def test_command_defaults_to_preview(self):
  from django.core.management import call_command
  from io import StringIO
  call_command('send_bill_reminders',stdout=StringIO())
  self.assertEqual(ReminderDelivery.objects.count(),0)

 def test_penalty_only_balance_is_still_eligible(self):
  self.tenant.penalty_type='percentage';self.tenant.custom_penalty_rate=12;self.tenant.save();self.tenant.refresh_from_db();self.bill.tenant=self.tenant
  Payment.objects.create(bill=self.bill,amount=100,payment_date=self.today)
  item=preview(self.today)[0][0]['items'][0]
  self.assertEqual(item['principal'],'0.00')
  self.assertGreater(float(item['penalty']),0)
 def test_invalid_review_id_is_validation_error_and_csrf_is_required(self):
  from django.test import Client
  user=User.objects.create_superuser('reminder-admin','admin@example.invalid','test-password')
  self.client.force_login(user)
  response=self.client.post('/admin/email-reminders/',{'action':'release','delivery':'invalid','confirmed_not_sent':'on'})
  self.assertEqual(response.status_code,200)
  secure=Client(enforce_csrf_checks=True);secure.force_login(user)
  self.assertEqual(secure.post('/admin/email-reminders/',{'action':'send','allottee':[str(self.tenant.uuid)]}).status_code,403)
 def test_uncertain_release_requires_confirmation(self):
  group=preview(self.today)[0][0]
  log=ReminderDelivery.objects.create(allottee_uuid=self.tenant.uuid,send_date=self.today,recipient=self.tenant.email,status='review',items=group['items'])
  user=User.objects.create_superuser('release-admin','admin@example.invalid','test-password');self.client.force_login(user)
  self.client.post('/admin/email-reminders/',{'action':'release','delivery':log.pk})
  log.refresh_from_db();self.assertEqual(log.status,'review')
  self.client.post('/admin/email-reminders/',{'action':'release','delivery':log.pk,'confirmed_not_sent':'on'})
  log.refresh_from_db();self.assertEqual(log.status,'failed');self.assertEqual(log.reviewed_by,user.username)
 def test_changed_smtp_configuration_pauses_automatic_sending(self):
  ReminderSettings.objects.create(automatic_enabled=True,verified_config=smtp_fingerprint())
  with override_settings(EMAIL_HOST_PASSWORD='changed-private-test-value'):
   result=send_reminders(today=self.today,automatic=True)
  self.assertIn('error',result);self.assertEqual(ReminderDelivery.objects.count(),0)
 def test_receipt_change_does_not_trigger_second_email_same_day(self):
  send_reminders(today=self.today)
  self.bill.issue_date+=dt.timedelta(days=1);self.bill.save()
  self.assertEqual(send_reminders(today=self.today)['accepted'],0)
 def test_unknown_backend_result_is_held_for_review(self):
  with patch('estate_app.reminders.service.EmailMessage.send',return_value=0):
   self.assertEqual(send_reminders(today=self.today)['review'],1)
 def test_unauthenticated_admin_does_not_expose_preview(self):
  response=self.client.get('/admin/email-reminders/')
  self.assertEqual(response.status_code,302);self.assertIn('/admin/login/',response.url)
 def test_duplicate_daily_claim_is_database_enforced(self):
  from django.db import IntegrityError,transaction
  values={'allottee_uuid':self.tenant.uuid,'send_date':self.today,'recipient':self.tenant.email}
  ReminderDelivery.objects.create(**values)
  with self.assertRaises(IntegrityError),transaction.atomic():
   ReminderDelivery.objects.create(**values)

from django.test import TransactionTestCase
from django.db import close_old_connections, OperationalError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
 EMAIL_HOST='smtp.gmail.com',EMAIL_PORT=587,EMAIL_USE_TLS=True,
 EMAIL_HOST_USER='sender@example.invalid',EMAIL_HOST_PASSWORD='test-only',
 DEFAULT_FROM_EMAIL='sender@example.invalid')
class ConcurrentReminderTests(TransactionTestCase):
 def test_parallel_senders_cannot_submit_duplicate_mail(self):
  today=timezone.localdate()
  tenant=Tenant.objects.create(name='Parallel test',type='Shop',email='parallel@example.invalid',penalty_type='none',gst_applicable=False)
  Bill.objects.create(tenant=tenant,month=1,year=2026,rent=100,issue_date=today-dt.timedelta(days=20))
  mail.get_connection();mail.outbox=[]
  barrier=Barrier(2)
  def attempt():
   close_old_connections()
   try:
    barrier.wait(timeout=10)
    return send_reminders(today=today)
   except OperationalError:
    return {'database_busy':True}
   finally:close_old_connections()
  with ThreadPoolExecutor(max_workers=2) as pool:
   results=list(pool.map(lambda _:attempt(),range(2)))
  self.assertLessEqual(len(mail.outbox),1)
  self.assertEqual(ReminderDelivery.objects.count(),1)
  log=ReminderDelivery.objects.get()
  if log.status in ('preparing','sending','review','accepted'):
   self.assertEqual(send_reminders(today=today)['accepted'],0)
