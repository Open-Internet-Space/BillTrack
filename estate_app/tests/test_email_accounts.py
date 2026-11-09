import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_HOST_USER='test@example.org', EMAIL_HOST_PASSWORD='test-only',
                   DEFAULT_FROM_EMAIL='test@example.org', ACCOUNT_EMAIL_ENABLED=True)
class EmailAccountTests(TestCase):
    password = 'An-office-passphrase-903!'

    def setUp(self):
        from estate_app.account_security import service
        self.recovery_dispatch = service.queue_recovery_mail
        dispatch = patch('estate_app.account_security.service.queue_recovery_mail', side_effect=service.deliver)
        dispatch.start()
        self.addCleanup(dispatch.stop)
        from estate_app.models import ReminderSettings
        from estate_app.reminders.service import smtp_fingerprint
        ReminderSettings.objects.create(verified_config=smtp_fingerprint())

    def code(self):
        return re.search(r'\b\d{6}\b', mail.outbox[-1].body).group()

    def signup(self):
        return self.client.post(reverse('account-signup'), {
            'name': 'Office User', 'email': 'Office@example.org',
            'password': self.password, 'password_confirm': self.password,
        })

    def test_signup_requires_verified_email_and_superuser_approval(self):
        from estate_app.models import AccountAccess
        self.signup()
        user = User.objects.get(email='office@example.org')
        self.assertFalse(user.is_active)
        response = self.client.post(reverse('account-signup'), {'action': 'verify', 'code': self.code()})
        self.assertContains(response, 'Awaiting superuser approval')
        access = AccountAccess.objects.get(user=user)
        self.assertEqual(access.verified_email, 'office@example.org')
        self.assertFalse(self.client.login(username=user.email, password=self.password))
        admin = User.objects.create_superuser('approver', 'boss@example.org', self.password)
        self.client.force_login(admin)
        response = self.client.post(reverse('account-approvals'), {'account': access.pk, 'decision': 'approve'})
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.profile.role, 'staff')
        self.assertTrue(self.client.login(username='OFFICE@example.org', password=self.password))

    def test_recovery_revokes_tokens_and_code_cannot_be_replayed(self):
        from estate_app.models import AccountAccess
        user = User.objects.create_user('legacy', 'legacy@example.org', self.password)
        from django.utils import timezone
        AccountAccess.objects.create(user=user, verified_email=user.email, verified_at=timezone.now())
        token = Token.objects.create(user=user)
        self.client.post(reverse('account-recovery'), {'email': user.email})
        code = self.code()
        response = self.client.post(reverse('account-recovery'), {
            'action': 'verify', 'code': code, 'password': self.password + 'new',
            'password_confirm': self.password + 'new',
        })
        self.assertContains(response, 'Password updated')
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.password + 'new'))
        self.assertContains(self.client.post(reverse('account-recovery'), {
            'action': 'verify', 'code': code, 'password': 'Different-passphrase-383!',
            'password_confirm': 'Different-passphrase-383!',
        }), 'invalid or expired')

    def test_legacy_verification_requires_current_password(self):
        from estate_app.models import AccountAccess
        User.objects.create_user('legacy', 'legacy@example.org', self.password)
        url = reverse('account-verify-email')
        self.client.post(url, {'username': 'legacy', 'password': 'wrong'})
        self.assertEqual(len(mail.outbox), 0)
        self.client.post(url, {'username': 'legacy', 'password': self.password})
        self.client.post(url, {'action': 'verify', 'code': self.code()})
        self.assertEqual(AccountAccess.objects.get(user__username='legacy').verified_email, 'legacy@example.org')

    @override_settings(ACCOUNT_EMAIL_ENABLED=False)
    def test_disabled_feature_sends_nothing(self):
        self.assertContains(self.signup(), 'Email account services are not available')
        self.assertFalse(User.objects.filter(email='office@example.org').exists())

    def test_unverified_accounts_cannot_be_approved(self):
        from estate_app.models import AccountAccess
        self.signup()
        access = AccountAccess.objects.get(user__email='office@example.org')
        admin = User.objects.create_superuser('approver', '', self.password)
        self.client.force_login(admin)
        self.client.post(reverse('account-approvals'), {'account': access.pk, 'decision': 'approve'})
        access.user.refresh_from_db()
        self.assertFalse(access.user.is_active)

    def test_smtp_failure_does_not_expose_secrets_or_activate_user(self):
        with patch('estate_app.account_security.service.send_mail', side_effect=OSError('secret-smtp-password')):
            response = self.signup()
        self.assertNotContains(response, 'secret-smtp-password')
        self.assertContains(response, 'could not be submitted')
        self.assertFalse(User.objects.get(email='office@example.org').is_active)

    def verified_user(self, username='legacy', email='legacy@example.org', **kwargs):
        from estate_app.models import AccountAccess
        from django.utils import timezone
        user = User.objects.create_user(username, email, self.password, **kwargs)
        AccountAccess.objects.create(user=user, verified_email=email, verified_at=timezone.now())
        return user

    def test_unknown_disabled_and_unverified_recovery_is_generic(self):
        url = reverse('account-recovery')
        self.verified_user(is_active=False)
        User.objects.create_user('unverified', 'unverified@example.org', self.password)
        for email in ['legacy@example.org', 'missing@example.org', 'unverified@example.org']:
            response = Client().post(url, {'email': email})
            self.assertContains(response, 'If the details are eligible')
        self.assertEqual(len(mail.outbox), 0)

    def test_ambiguous_email_and_username_aliases_fail_closed(self):
        first = self.verified_user()
        User.objects.create_user('other', 'LEGACY@example.org', self.password)
        self.assertFalse(self.client.login(username=first.email, password=self.password))
        self.client.post(reverse('account-recovery'), {'email': first.email})
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(self.client.login(username='legacy', password=self.password))

    def test_changing_email_clears_verification_and_invalidates_code(self):
        user = self.verified_user()
        self.client.post(reverse('account-recovery'), {'email': user.email})
        code = self.code()
        user.email = 'new@example.org'
        user.save()
        user.account_access.refresh_from_db()
        self.assertIsNone(user.account_access.verified_email)
        response = self.client.post(reverse('account-recovery'), {'action': 'verify', 'code': code,
                                    'password': self.password+'new', 'password_confirm': self.password+'new'})
        self.assertContains(response, 'invalid or expired')

    def test_resend_invalidates_old_code_and_keeps_attempt_budget(self):
        from estate_app.account_security import service
        user = self.verified_user()
        with patch('estate_app.account_security.service.time.time', return_value=2000000000):
            first = service.issue('recovery', user.email, user)
            old_code = self.code()
            for _ in range(4):
                service.verification_budget(first, 'recovery')
            second = service.issue('recovery', user.email, user)
            service.verification_budget(second, 'recovery')
            with self.assertRaises(service.AccountError):
                service.verification_budget(second, 'recovery')
            with self.assertRaises(service.AccountError):
                service.consume(first, 'recovery', old_code)

    def test_expired_cross_purpose_and_password_changed_codes_fail(self):
        from estate_app.account_security import service
        user = self.verified_user()
        with patch('estate_app.account_security.service.time.time', return_value=2000000000):
            nonce = service.issue('recovery', user.email, user)
            code = self.code()
            with self.assertRaises(service.AccountError):
                service.consume(nonce, 'signup', code)
        with patch('estate_app.account_security.service.time.time', return_value=2000000600):
            with self.assertRaises(service.AccountError):
                service.consume(nonce, 'recovery', code)
        nonce = service.issue('recovery', user.email, user)
        code = self.code()
        user.set_password('Changed-password-785!')
        user.save()
        with self.assertRaises(service.AccountError):
            service.consume(nonce, 'recovery', code)

    def test_wrong_guesses_are_counted_despite_transaction_rollback(self):
        from estate_app.models import AccountRateLimit
        user = self.verified_user()
        self.client.post(reverse('account-recovery'), {'email': user.email})
        correct = self.code()
        wrong = '000000' if correct != '000000' else '111111'
        for _ in range(5):
            self.client.post(reverse('account-recovery'), {'action': 'verify', 'code': wrong,
                             'password': self.password+'new', 'password_confirm': self.password+'new'})
        response = self.client.post(reverse('account-recovery'), {'action': 'verify', 'code': correct,
                                    'password': self.password+'new', 'password_confirm': self.password+'new'})
        self.assertContains(response, 'Too many attempts')
        self.assertTrue(AccountRateLimit.objects.filter(attempts=5).exists())
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.password))

    def test_send_limits_survive_new_sessions_and_different_ips(self):
        self.verified_user()
        url = reverse('account-recovery')
        self.client.post(url, {'email': 'legacy@example.org'})
        response = Client().post(url, {'email': 'LEGACY@example.org'}, REMOTE_ADDR='10.0.0.2')
        self.assertContains(response, 'Too many attempts')
        self.assertEqual(len(mail.outbox), 1)

    def test_pending_account_cannot_bypass_approval_by_active_flag_or_token(self):
        self.signup()
        user = User.objects.get(email='office@example.org')
        user.is_active = True
        user.save()
        self.assertFalse(self.client.login(username=user.email, password=self.password))
        token = Token.objects.create(user=user)
        response = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION='Token '+token.key)
        self.assertEqual(response.status_code, 401)

    def test_approval_is_superuser_only_and_decision_cannot_be_replayed(self):
        from estate_app.models import AccountAccess
        from estate_app.account_security.service import AccountError, decide
        self.signup()
        self.client.post(reverse('account-signup'), {'action': 'verify', 'code': self.code()})
        access = AccountAccess.objects.get(user__email='office@example.org')
        staff = User.objects.create_user('staff', password=self.password, is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('account-approvals')).status_code, 403)
        boss = User.objects.create_superuser('boss', '', self.password)
        decide(access.pk, boss, 'reject')
        with self.assertRaises(AccountError):
            decide(access.pk, boss, 'approve')
        access.user.refresh_from_db()
        self.assertFalse(access.user.is_active)

    def test_recovery_invalidates_existing_sessions_and_requires_new_login(self):
        user = self.verified_user()
        other = Client()
        self.assertTrue(other.login(username=user.username, password=self.password))
        self.client.post(reverse('account-recovery'), {'email': user.email})
        self.client.post(reverse('account-recovery'), {'action': 'verify', 'code': self.code(),
                         'password': self.password+'new', 'password_confirm': self.password+'new'})
        from django.contrib.auth import get_user
        request = other.get(reverse('account-recovery')).wsgi_request
        self.assertFalse(get_user(request).is_authenticated)

    def test_sensitive_forms_have_csrf_no_cache_and_never_reflect_passwords(self):
        url = reverse('account-signup')
        self.assertEqual(Client(enforce_csrf_checks=True).post(url, {}).status_code, 403)
        response = self.signup()
        self.assertIn('no-store', response['Cache-Control'])
        self.assertNotContains(response, self.password)
        self.assertNotContains(response, 'value="'+self.code()+'"')

    def test_smtp_config_change_disables_feature_until_retested(self):
        with override_settings(EMAIL_HOST_PASSWORD='changed-test-only'):
            response = self.signup()
        self.assertContains(response, 'Email account services are not available')
        self.assertFalse(User.objects.filter(email='office@example.org').exists())

    def test_correct_pending_credentials_show_status_without_token(self):
        self.signup()
        response = self.client.post('/api/auth/login/', {'username': 'office@example.org', 'password': self.password})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Verify your signup email', status_code=403)
        self.assertNotIn('token', response.json())

    def test_signup_password_must_not_match_name_or_email(self):
        response = self.client.post(reverse('account-signup'), {'name': 'abcdefghijk', 'email': 'abcdefghijk@example.org',
                                    'password': 'abcdefghijk', 'password_confirm': 'abcdefghijk'})
        self.assertFalse(User.objects.filter(email='abcdefghijk@example.org').exists())
        self.assertContains(response, 'too similar')

    def test_stale_unverified_application_expires_without_deleting_account(self):
        from django.utils import timezone
        from datetime import timedelta
        from estate_app.account_security.service import expire_applications
        self.signup()
        user = User.objects.get(email='office@example.org')
        User.objects.filter(pk=user.pk).update(date_joined=timezone.now()-timedelta(days=2))
        expire_applications()
        user.refresh_from_db()
        self.assertEqual(user.email, '')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_active)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_unverified_application_is_absent_from_approval_queue(self):
        self.signup()
        boss = User.objects.create_superuser('boss', '', self.password)
        self.client.force_login(boss)
        self.assertNotContains(self.client.get(reverse('account-approvals')), 'office@example.org')

    def test_rollback_preparation_preserves_legacy_users_and_quarantines_signups(self):
        from django.core.management import call_command
        from io import StringIO
        from estate_app.models import AccountAccess
        legacy = self.verified_user()
        self.signup()
        user = User.objects.get(email='office@example.org')
        User.objects.filter(pk=user.pk).update(is_active=True)
        Token.objects.create(user=user)
        call_command('prepare_account_rollback', stdout=StringIO())
        self.assertTrue(User.objects.get(pk=user.pk).is_active)
        call_command('prepare_account_rollback', apply=True, stdout=StringIO())
        self.assertFalse(User.objects.get(pk=user.pk).is_active)
        self.assertFalse(Token.objects.filter(user=user).exists())
        self.assertTrue(User.objects.get(pk=legacy.pk).is_active)

    def test_recovery_dispatch_does_not_wait_for_smtp(self):
        from estate_app.account_security import service
        from threading import Event
        started, release, finished = Event(), Event(), Event()
        def blocked_delivery(*args):
            started.set()
            release.wait(timeout=5)
            finished.set()
        # Exercise the real dispatcher independently of the synchronous mailbox fixture.
        with patch.object(service, 'deliver', side_effect=blocked_delivery):
            try:
                self.recovery_dispatch('legacy@example.org', '123456', 'recovery')
                self.assertTrue(started.wait(timeout=2))
                self.assertFalse(finished.is_set())
            finally:
                release.set()
                self.assertTrue(finished.wait(timeout=2))

    def test_malformed_login_input_returns_controlled_errors(self):
        for username in [123, [], {}, None, 'x'*255]:
            response = self.client.post('/api/auth/login/', {'username': username, 'password': self.password}, content_type='application/json')
            self.assertEqual(response.status_code, 401)
        response = self.client.post('/api/auth/login/', ['not', 'an', 'object'], content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_signup_email_change_releases_reservation_and_keeps_rollback_provenance(self):
        self.signup()
        user = User.objects.get(email='office@example.org')
        user.email = 'changed@example.org'
        user.save()
        user.account_access.refresh_from_db()
        self.assertIsNone(user.account_access.signup_email)
        self.assertTrue(user.account_access.signup_created)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   EMAIL_HOST_USER='test@example.org', EMAIL_HOST_PASSWORD='test-only',
                   DEFAULT_FROM_EMAIL='test@example.org', ACCOUNT_EMAIL_ENABLED=True)
class ConcurrentEmailAccountTests(TransactionTestCase):
    def parallel(self, action):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from estate_app.account_security.service import AccountError
        barrier = Barrier(2)
        def run():
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                action()
                return 'success'
            except AccountError:
                return 'rejected'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(run) for _ in range(2)]
            return sorted(f.result(timeout=30) for f in futures)

    def test_only_one_concurrent_reset_can_consume_a_code(self):
        from estate_app.account_security import service
        from estate_app.models import AccountAccess
        from django.utils import timezone
        user = User.objects.create_user('legacy', 'legacy@example.org', 'Old-password-728!')
        AccountAccess.objects.create(user=user, verified_email=user.email, verified_at=timezone.now())
        with patch.object(service, 'queue_recovery_mail'), patch.object(service.secrets, 'randbelow', return_value=123456):
            nonce = service.issue('recovery', user.email, user)
        self.assertEqual(self.parallel(lambda: service.consume(nonce, 'recovery', '123456', 'New-passphrase-821!')),
                         ['rejected', 'success'])

    def test_only_one_concurrent_approval_succeeds(self):
        from estate_app.account_security import service
        from estate_app.models import AccountAccess
        from django.utils import timezone
        user = User.objects.create_user('applicant', 'applicant@example.org', 'Old-password-728!', is_active=False)
        access = AccountAccess.objects.create(user=user, status='pending', signup_email=user.email,
                                              verified_email=user.email, verified_at=timezone.now())
        boss = User.objects.create_superuser('boss', '', 'Boss-passphrase-982!')
        self.assertEqual(self.parallel(lambda: service.decide(access.pk, boss, 'approve')), ['rejected', 'success'])
