import json
from django.contrib.auth.models import User
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from estate_app.models import Bill, Payment, Tenant


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class ActivityTests(TestCase):
    def test_bulk_cascade_snapshots_and_deleted_actor(self):
        from estate_app.models import ActivityEntry
        from estate_app.activity.context import operation
        actor = User.objects.create_superuser('auditor', 'audit@example.invalid', 'secret-password')
        with operation(actor=actor, source='admin', reason='Correct duplicate allotment'):
            tenant = Tenant.objects.create(name='Original', type='Shop', gst_applicable=False)
            bill = Bill.objects.create(tenant=tenant, year=2026, month=1, rent=100)
            payment = Payment.objects.create(bill=bill, amount=10, recorded_by=actor)
            Tenant.objects.filter(pk=tenant.pk).update(name='Corrected')
            tenant.delete()
        actor.delete()
        changed = ActivityEntry.objects.get(record_type='estate_app.tenant', action='update')
        self.assertEqual(changed.before['name'], 'Original')
        self.assertEqual(changed.after['name'], 'Corrected')
        self.assertEqual(changed.actor_name, 'auditor')
        deleted = ActivityEntry.objects.filter(action='delete', reason='Correct duplicate allotment')
        self.assertEqual(set(deleted.values_list('record_type', flat=True)),
                         {'estate_app.tenant', 'estate_app.bill', 'estate_app.payment'})
        self.assertEqual(deleted.get(record_type='estate_app.payment').before['amount'], 10)

    def test_secret_changes_are_excluded_and_history_is_immutable(self):
        from estate_app.models import ActivityEntry
        user = User.objects.create_user('safe-account', password='sentinel-password')
        count = ActivityEntry.objects.count()
        user.set_password('another-sentinel'); user.save(update_fields=['password'])
        self.assertEqual(ActivityEntry.objects.count(), count)
        content = json.dumps(list(ActivityEntry.objects.values('before', 'after')))
        self.assertNotIn('password', content)
        self.assertNotIn('pbkdf2', content)
        for mutate in (lambda: ActivityEntry.objects.update(reason='tampered'),
                       lambda: ActivityEntry.objects.all().delete()):
            with self.assertRaises(DatabaseError), transaction.atomic():
                mutate()

    def test_business_and_audit_roll_back_together(self):
        from estate_app.models import ActivityEntry
        from estate_app.activity.context import operation
        count = ActivityEntry.objects.count()
        with self.assertRaises(RuntimeError):
            with operation(source='import', reason='Rejected import'), transaction.atomic():
                Tenant.objects.create(name='Must roll back', type='Shop')
                raise RuntimeError('abort')
        self.assertFalse(Tenant.objects.filter(name='Must roll back').exists())
        self.assertEqual(ActivityEntry.objects.count(), count)
        with connection.cursor() as cursor:
            cursor.execute("CREATE TEMP TRIGGER reject_audit BEFORE INSERT ON estate_app_activityentry BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END")
        try:
            with self.assertRaises(DatabaseError), transaction.atomic():
                Tenant.objects.create(name='Audit failure', type='Shop')
            self.assertFalse(Tenant.objects.filter(name='Audit failure').exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute('DROP TRIGGER reject_audit')

    def test_reused_integer_id_has_distinct_record_history(self):
        from estate_app.models import ActivityEntry
        user = User.objects.create_user('old-user')
        pk = user.pk
        user.delete()
        User.objects.create(id=pk, username='new-user')
        entries = ActivityEntry.objects.filter(record_type='auth.user', record_id=str(pk), action='create')
        self.assertEqual(entries.values('record_identity').distinct().count(), 2)

    def test_bulk_payment_changes_refresh_both_bills_and_rollback(self):
        from unittest.mock import patch
        from decimal import Decimal
        tenant = Tenant.objects.create(name='Payment correction', type='Shop', gst_applicable=False)
        old = Bill.objects.create(tenant=tenant, year=2026, month=1, rent=100)
        new = Bill.objects.create(tenant=tenant, year=2026, month=2, rent=100)
        payment = Payment.objects.create(bill=old, amount=100)
        Payment.objects.filter(pk=payment.pk).update(bill=new)
        old.refresh_from_db(); new.refresh_from_db()
        self.assertEqual((old.status, new.status), ('Unpaid', 'Paid'))
        with patch.object(Bill, 'update_status', side_effect=RuntimeError('recalculation failed')):
            with self.assertRaises(RuntimeError):
                Payment.objects.filter(pk=payment.pk).update(amount=50)
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal('100'))
        Payment.objects.filter(pk=payment.pk).delete()
        new.refresh_from_db()
        self.assertEqual(new.status, 'Unpaid')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       EMAIL_HOST_USER='sender@example.invalid', EMAIL_HOST_PASSWORD='test-only',
                       DEFAULT_FROM_EMAIL='sender@example.invalid')
    def test_reminder_edits_deletions_cannot_release_submission(self):
        import datetime as dt
        from django.utils import timezone
        from django.core import mail
        from estate_app.models import ReminderDelivery
        from estate_app.tests.test_reminders import send_reviewed
        from estate_app.reminders.service import preview
        today = timezone.localdate()
        tenant = Tenant.objects.create(name='Protected send', type='Shop', email='allottee@example.invalid', gst_applicable=False, penalty_type='none')
        Bill.objects.create(tenant=tenant, month=1, year=2026, rent=100, issue_date=today-dt.timedelta(days=20))
        self.assertEqual(send_reviewed(today)['accepted'], 1)
        delivery = ReminderDelivery.objects.get()
        delivery.status = 'failed'; delivery.items = []; delivery.save()
        self.assertEqual(preview(today)[0], [])
        delivery.delete()
        self.assertEqual(preview(today)[0], [])
        self.assertEqual(send_reviewed(today)['accepted'], 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_api_reason_authenticated_actor_and_deletion_confirmation(self):
        from rest_framework.test import APIClient
        from estate_app.models import ActivityEntry
        user = User.objects.create_superuser('api-auditor', 'api@example.invalid', 'test-password')
        client = APIClient(); client.force_authenticate(user)
        tenant = Tenant.objects.create(name='Before API', type='Shop', gst_applicable=False)
        url = f'/api/tenants/{tenant.pk}/'
        self.assertEqual(client.patch(url, {'name': 'After API'}, format='json').status_code, 400)
        self.assertEqual(client.patch(url, {'name': 'After API', 'change_reason': 'Correct spelling'}, format='json').status_code, 200)
        entry = ActivityEntry.objects.filter(record_type='estate_app.tenant', action='update').latest('id')
        self.assertEqual((entry.actor_name, entry.source, entry.reason), ('api-auditor', 'api', 'Correct spelling'))
        self.assertEqual(client.delete(url, HTTP_X_CHANGE_REASON='Remove duplicate').status_code, 400)
        preview = client.get(url+'deletion-preview/').data
        self.assertEqual(client.delete(url, HTTP_X_CHANGE_REASON='Remove duplicate', HTTP_X_DELETION_CONFIRMATION=preview['confirmation']).status_code, 204)

    def test_admin_required_reason_bulk_delete_and_read_only_history(self):
        from estate_app.models import ActivityEntry, ReminderDelivery
        import datetime as dt
        user = User.objects.create_superuser('admin-auditor', 'admin@example.invalid', 'test-password')
        self.client.force_login(user)
        delivery = ReminderDelivery.objects.create(allottee_uuid='00000000-0000-0000-0000-000000000001',
            allottee_name='Original evidence', send_date=dt.date(2026, 1, 1), recipient='a@example.invalid', status='accepted')
        url = f'/admin/estate_app/reminderdelivery/{delivery.pk}/delete/'
        preview = self.client.get(url)
        self.assertContains(preview, 'Reason')
        self.client.post(url, {'post': 'yes'})
        self.assertTrue(ReminderDelivery.objects.filter(pk=delivery.pk).exists())
        preview = self.client.get(url)
        self.client.post(url, {'post': 'yes', 'change_reason': 'Remove misleading visible row', 'confirmation': preview.context['confirmation']})
        self.assertFalse(ReminderDelivery.objects.exists())
        entry = ActivityEntry.objects.filter(record_type='estate_app.reminderdelivery', action='delete').get()
        detail = self.client.get(f'/admin/estate_app/activityentry/{entry.pk}/change/')
        self.assertContains(detail, 'Original evidence')
        self.assertNotContains(detail, 'name="_save"')
        self.assertEqual(self.client.post(f'/admin/estate_app/activityentry/{entry.pk}/delete/').status_code, 403)
        user.is_superuser = False; user.save()
        self.assertEqual(self.client.get('/admin/estate_app/activityentry/').status_code, 403)

    def test_admin_edit_reasons_and_bulk_cascade_preview(self):
        from estate_app.models import ActivityEntry
        user = User.objects.create_superuser('correction-admin', 'admin@example.invalid', 'test-password')
        self.client.force_login(user)
        tenant = Tenant.objects.create(name='Bulk original', type='Shop', gst_applicable=False)
        bill = Bill.objects.create(tenant=tenant, month=1, year=2026, rent=100)
        Payment.objects.create(bill=bill, amount=25)
        url = f'/admin/estate_app/tenant/{tenant.pk}/change/'
        form = self.client.get(url).context['adminform'].form
        data = {key: value for key, value in form.initial.items() if value is not None}
        data.update(name='Corrected name', penalty_type='none', type='Shop')
        self.client.post(url, data)
        tenant.refresh_from_db(); self.assertEqual(tenant.name, 'Bulk original')
        data['change_reason'] = 'Fix registered business name'
        self.assertEqual(self.client.post(url, data).status_code, 302)
        entry = ActivityEntry.objects.filter(record_type='estate_app.tenant', action='update').latest('id')
        self.assertEqual(entry.reason, 'Fix registered business name')
        selection = {'action': 'delete_selected', '_selected_action': [str(tenant.pk)]}
        preview = self.client.post('/admin/estate_app/tenant/', selection)
        self.assertContains(preview, 'Payment')
        self.client.post('/admin/estate_app/tenant/', {**selection, 'post': 'yes'})
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())
        response = self.client.post('/admin/estate_app/tenant/', {**selection, 'post': 'yes',
            'change_reason': 'Remove duplicated allotment and its records', 'confirmation': preview.context['confirmation']})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_stale_deletion_preview_cannot_delete_new_children(self):
        from rest_framework.test import APIClient
        user = User.objects.create_superuser('stale-check', 'stale@example.invalid', 'test-password')
        api = APIClient(); api.force_authenticate(user)
        tenant = Tenant.objects.create(name='Concurrent update', type='Shop', gst_applicable=False)
        bill = Bill.objects.create(tenant=tenant, year=2026, month=1, rent=100)
        url = f'/api/bills/{bill.pk}/'
        token = api.get(url+'deletion-preview/').data['confirmation']
        Payment.objects.create(bill=bill, amount=10)
        response = api.delete(url, HTTP_X_CHANGE_REASON='Remove mistake', HTTP_X_DELETION_CONFIRMATION=token)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Bill.objects.filter(pk=bill.pk).exists())

    def test_inline_payment_deletion_requires_effect_preview(self):
        user = User.objects.create_superuser('inline-admin', 'inline@example.invalid', 'test-password')
        self.client.force_login(user)
        tenant = Tenant.objects.create(name='Inline example', type='Shop', gst_applicable=False)
        bill = Bill.objects.create(tenant=tenant, month=1, year=2026, rent=100)
        payment = Payment.objects.create(bill=bill, amount=25)
        response = self.client.post(f'/admin/estate_app/bill/{bill.pk}/change/', {
            'payments-TOTAL_FORMS': '1', 'payments-INITIAL_FORMS': '1',
            'payments-0-id': payment.pk, 'payments-0-DELETE': 'on', 'change_reason': 'Remove duplicate receipt'})
        self.assertContains(response, 'Confirm inline deletions')
        self.assertContains(response, 'Recalculate status and balance')
        self.assertTrue(Payment.objects.filter(pk=payment.pk).exists())

    def test_security_sentinels_are_absent_and_token_actor_does_not_leak(self):
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient
        from estate_app.models import ActivityEntry, AccountAuthenticator, EmailChallenge, ReminderSettings
        first = User.objects.create_user('token-actor', password='sentinel-password')
        AccountAuthenticator.objects.create(user=first, secret='sentinel-authenticator-seed')
        EmailChallenge.objects.create(key='sentinel-otp-key', user=first, purpose='recovery', email='a@example.invalid',
            digest='sentinel-otp-digest', password_stamp='sentinel-password-stamp', expires_at=9999999999)
        ReminderSettings.objects.create(verified_config='sentinel-smtp-fingerprint')
        token = Token.objects.create(user=first, key='sentinel-session-token')
        tenant = Tenant.objects.create(name='Token example', type='Shop')
        api = APIClient(); api.credentials(HTTP_AUTHORIZATION='Token '+token.key)
        self.assertEqual(api.patch(f'/api/tenants/{tenant.pk}/', {'name': 'Token edit', 'change_reason': 'Fix name'}, format='json').status_code, 200)
        entry = ActivityEntry.objects.filter(record_type='estate_app.tenant', action='update').latest('id')
        self.assertEqual(entry.actor_name, 'token-actor')
        Tenant.objects.filter(pk=tenant.pk).update(name='Background edit')
        self.assertEqual(ActivityEntry.objects.latest('id').actor_name, '')
        stored = json.dumps(list(ActivityEntry.objects.values('before', 'after', 'reason')))
        for secret in ['sentinel-', first.password]:
            self.assertNotIn(secret, stored)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       EMAIL_HOST_USER='sender@example.invalid', EMAIL_HOST_PASSWORD='sentinel-smtp-password',
                       DEFAULT_FROM_EMAIL='sender@example.invalid')
    def test_accepted_mail_with_failed_outcome_save_remains_blocked_and_review_survives_deletion(self):
        import datetime as dt
        from unittest.mock import patch
        from django.utils import timezone
        from django.core import mail
        from estate_app.models import ReminderDelivery, ReminderSubmission, ActivityEntry
        from estate_app.reminders.service import save_submission, preview
        from estate_app.tests.test_reminders import send_reviewed
        today = timezone.localdate()
        tenant = Tenant.objects.create(name='Uncertain outcome', type='Shop', email='recipient@example.invalid', penalty_type='none', gst_applicable=False)
        Bill.objects.create(tenant=tenant, month=1, year=2026, rent=100, issue_date=today-dt.timedelta(days=20))
        def fail_outcome(log):
            if log.status == 'accepted':
                raise DatabaseError('simulated outcome persistence failure')
            return save_submission(log)
        with patch('estate_app.reminders.service.save_submission', side_effect=fail_outcome):
            with self.assertRaises(DatabaseError):
                send_reviewed(today)
        self.assertEqual(len(mail.outbox), 1)
        submission = ReminderSubmission.objects.get()
        self.assertEqual(submission.status, 'sending')
        self.assertEqual(submission.message['body'], mail.outbox[0].body)
        ReminderDelivery.objects.all().delete()
        self.assertEqual(preview(today)[0], [])
        user = User.objects.create_superuser('provider-reviewer', 'review@example.invalid', 'test-password')
        self.client.force_login(user)
        self.client.post('/admin/email-reminders/', {'action': 'release', 'submission': submission.pk, 'confirmed_not_sent': 'on'})
        submission.refresh_from_db(); self.assertEqual(submission.status, 'sending')
        self.client.post('/admin/email-reminders/', {'action': 'release', 'submission': submission.pk,
            'confirmed_not_sent': 'on', 'change_reason': 'Provider confirms no actual submission; synthetic failure test'})
        submission.refresh_from_db(); self.assertEqual(submission.status, 'failed')
        self.assertFalse(ReminderDelivery.objects.exists())
        self.assertTrue(ActivityEntry.objects.filter(reason='Provider confirms no actual submission; synthetic failure test').exists())
        self.assertNotIn('sentinel-smtp-password', json.dumps(list(ActivityEntry.objects.values('before', 'after'))))

    def test_bulk_create_update_and_raw_sql_are_audited(self):
        from estate_app.models import ActivityEntry
        from estate_app.activity.context import operation
        tenant = Tenant.objects.create(name='Bulk payment test', type='Shop', gst_applicable=False)
        bill = Bill.objects.create(tenant=tenant, year=2026, month=1, rent=100)
        with operation(source='background', reason='Reconcile synthetic receipts'):
            payments = Payment.objects.bulk_create([Payment(bill=bill, amount=25), Payment(bill=bill, amount=75)])
            bill.refresh_from_db(); self.assertEqual(bill.status, 'Paid')
            payments[0].amount = 10
            Payment.objects.bulk_update(payments, ['amount'])
            bill.refresh_from_db(); self.assertEqual(bill.status, 'Partial')
            with connection.cursor() as cursor:
                cursor.execute('UPDATE estate_app_tenant SET name=%s WHERE id=%s', ['SQL update', tenant.pk])
        self.assertTrue(ActivityEntry.objects.filter(source='background', reason='Reconcile synthetic receipts',
            record_type='estate_app.tenant', action='update', after__name='SQL update').exists())

    def test_bulk_history_creation_establishes_protected_evidence(self):
        import datetime as dt
        from estate_app.models import ReminderDelivery, ReminderSubmission
        ReminderDelivery.objects.bulk_create([ReminderDelivery(allottee_uuid='00000000-0000-0000-0000-000000000001',
            allottee_name='Bulk accepted', send_date=dt.date(2026, 1, 1), recipient='a@example.invalid', status='accepted')])
        ReminderDelivery.objects.all().delete()
        self.assertEqual(ReminderSubmission.objects.get().status, 'accepted')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       EMAIL_HOST_USER='sender@example.invalid', EMAIL_HOST_PASSWORD='test-only',
                       DEFAULT_FROM_EMAIL='sender@example.invalid')
    def test_provider_review_cannot_release_active_smtp_worker(self):
        import datetime as dt
        from unittest.mock import patch
        from django.utils import timezone
        from django.core import mail
        from estate_app.models import ReminderSubmission
        from estate_app.tests.test_reminders import send_reviewed
        from estate_app.reminders.delivery import send_message
        user = User.objects.create_superuser('race-reviewer', 'race@example.invalid', 'test-password')
        self.client.force_login(user)
        today = timezone.localdate()
        tenant = Tenant.objects.create(name='Race reminder', type='Shop', email='recipient@example.invalid', penalty_type='none', gst_applicable=False)
        Bill.objects.create(tenant=tenant, month=1, year=2026, rent=100, issue_date=today-dt.timedelta(days=20))
        calls = []
        observed = []
        def submit(message, connection):
            calls.append(1)
            if len(calls) == 1:
                submission = ReminderSubmission.objects.get()
                self.client.post('/admin/email-reminders/', {'action': 'release', 'submission': submission.pk,
                    'confirmed_not_sent': 'on', 'change_reason': 'Attempt unsafe active release'})
                submission.refresh_from_db()
                observed.append((submission.status, send_reviewed(today)['accepted']))
            return send_message(message, connection)
        with patch('estate_app.reminders.service.send_message', side_effect=submit):
            self.assertEqual(send_reviewed(today)['accepted'], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(observed, [('sending', 0)])
        self.assertEqual(len(mail.outbox), 1)

    def test_stale_submission_worker_cannot_resume_released_claim(self):
        import datetime as dt
        from estate_app.models import ReminderSubmission
        from estate_app.reminders.service import save_submission
        from django.core.exceptions import ValidationError
        old = ReminderSubmission.objects.create(allottee_uuid='00000000-0000-0000-0000-000000000001',
            allottee_name='Old worker', send_date=dt.date(2026, 1, 1), recipient='a@example.invalid')
        save_submission(old)
        ReminderSubmission.objects.filter(pk=old.pk).update(status='failed')
        old.status = 'sending'
        with self.assertRaises(ValidationError):
            save_submission(old)
        ReminderSubmission.objects.filter(pk=old.pk).update(status='preparing', attempts=2)
        with self.assertRaises(ValidationError):
            save_submission(old)
