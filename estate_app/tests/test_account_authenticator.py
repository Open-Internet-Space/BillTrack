import base64
import hashlib
import hmac
import struct
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token


def code_for(secret, counter=66666666):
    key = base64.b32decode(secret)
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = (struct.unpack('>I', digest[offset:offset+4])[0] & 0x7fffffff) % 1000000
    return f'{value:06d}'


@override_settings(TOTP_RESET_SECRET='', ACCOUNT_EMAIL_ENABLED=False)
@patch('time.time', return_value=2000000000)
class AccountAuthenticatorTests(TestCase):
    password = 'Office-passphrase-736!'

    def setUp(self):
        self.user = User.objects.create_user('ordinary', 'ordinary@example.org', self.password)

    def test_ordinary_user_can_enroll_and_reset_by_email_without_smtp(self, clock):
        from estate_app.models import AccountAuthenticator
        url = reverse('account-authenticator')
        self.client.post(url, {'username': self.user.email, 'password': self.password})
        secret = self.client.session['authenticator_setup']['secret']
        response = self.client.post(url, {'action': 'confirm', 'code': code_for(secret)})
        self.assertContains(response, 'Authenticator recovery is ready')
        self.assertTrue(AccountAuthenticator.objects.filter(user=self.user).exists())
        token = Token.objects.create(user=self.user)
        clock.return_value = 2000000030
        response = self.client.post(reverse('totp-password-reset'), {
            'username': self.user.email.upper(), 'code': code_for(secret, 66666667),
            'password': self.password+'new', 'password_confirm': self.password+'new',
        })
        self.assertContains(response, 'Password updated')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password+'new'))
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_installation_emergency_secret_is_not_shared_with_ordinary_users(self, clock):
        with override_settings(TOTP_RESET_SECRET='JBSWY3DPEHPK3PXP'):
            response = self.client.post(reverse('totp-password-reset'), {
                'username': self.user.username, 'code': code_for('JBSWY3DPEHPK3PXP'),
                'password': self.password+'new', 'password_confirm': self.password+'new',
            })
        self.assertContains(response, 'invalid')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_pending_and_disabled_users_cannot_enroll(self, clock):
        from estate_app.models import AccountAccess, AccountAuthenticator
        AccountAccess.objects.create(user=self.user, status='pending')
        self.assertContains(self.client.post(reverse('account-authenticator'), {
            'username': self.user.username, 'password': self.password}), 'Invalid credentials')
        self.assertNotIn('authenticator_setup', self.client.session)
        self.assertFalse(AccountAuthenticator.objects.exists())

    def test_setup_requires_password_and_current_code_and_rejects_replay(self, clock):
        from estate_app.models import AccountAuthenticator
        url = reverse('account-authenticator')
        self.client.post(url, {'username': self.user.username, 'password': 'wrong'})
        self.assertNotIn('authenticator_setup', self.client.session)
        self.client.post(url, {'username': self.user.username, 'password': self.password})
        secret = self.client.session['authenticator_setup']['secret']
        self.client.post(url, {'action': 'confirm', 'code': code_for(secret)})
        response = self.client.post(reverse('totp-password-reset'), {
            'username': self.user.username, 'code': code_for(secret),
            'password': self.password+'new', 'password_confirm': self.password+'new',
        })
        self.assertContains(response, 'invalid')
        self.assertEqual(AccountAuthenticator.objects.count(), 1)

    def test_both_recovery_choices_are_visible_without_smtp(self, clock):
        response = self.client.get(reverse('totp-password-reset'))
        self.assertContains(response, reverse('account-recovery'))
        self.assertContains(response, reverse('account-authenticator'))
        self.assertContains(response, 'Username or email')
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('account-authenticator'), {}).status_code, 403)

    def test_disabled_or_pending_account_cannot_reset_with_enrolled_code(self, clock):
        from estate_app.models import AccountAccess, AccountAuthenticator
        secret = 'JBSWY3DPEHPK3PXP'
        AccountAuthenticator.objects.create(user=self.user, secret=secret)
        access = AccountAccess.objects.create(user=self.user, status='pending')
        data = {'username': self.user.email, 'code': code_for(secret), 'password': self.password+'new', 'password_confirm': self.password+'new'}
        self.assertContains(self.client.post(reverse('totp-password-reset'), data), 'invalid')
        access.status = 'approved'; access.save()
        self.user.is_active = False; self.user.save()
        self.assertContains(self.client.post(reverse('totp-password-reset'), data), 'invalid')
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(self.password))

    def test_setup_expires_and_cannot_replace_existing_authenticator(self, clock):
        from estate_app.models import AccountAuthenticator
        url = reverse('account-authenticator')
        data = {'username': self.user.email, 'password': self.password}
        self.client.post(url, data)
        secret = self.client.session['authenticator_setup']['secret']
        clock.return_value = 2000000600
        self.assertContains(self.client.get(url), 'Setup expired')
        self.assertFalse(AccountAuthenticator.objects.exists())
        original = AccountAuthenticator.objects.create(user=self.user, secret='JBSWY3DPEHPK3PXP')
        response = self.client.post(url, data)
        self.assertContains(response, 'already configured')
        self.assertNotContains(response, original.secret)
        self.assertNotContains(response, secret)

    def test_username_and_email_share_recovery_attempt_budget(self, clock):
        from estate_app.models import AccountAuthenticator
        AccountAuthenticator.objects.create(user=self.user, secret='JBSWY3DPEHPK3PXP')
        for identifier in [self.user.username, self.user.email, self.user.email.upper(), self.user.username, self.user.email]:
            response = Client().post(reverse('totp-password-reset'), {'username': identifier, 'code': 'invalid'})
            self.assertEqual(response.status_code, 200)
        response = Client().post(reverse('totp-password-reset'), {'username': self.user.username})
        self.assertEqual(response.status_code, 429)

    def test_legacy_fallback_rechecks_eligibility_after_code_validation(self, clock):
        from estate_app.account_security import service, totp
        self.user.is_staff = True
        self.user.save()
        def disable_during_validation(*args):
            User.objects.filter(pk=self.user.pk).update(is_active=False)
            return True
        with override_settings(TOTP_RESET_SECRET='JBSWY3DPEHPK3PXP'):
            with self.assertRaises(service.AccountError):
                totp.reset_password(self.user, code_for('JBSWY3DPEHPK3PXP'), self.password+'new', self.password+'new', disable_during_validation)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))


class ConcurrentAuthenticatorTests(TransactionTestCase):
    def test_only_one_reset_can_use_a_personal_authenticator_code(self):
        import time
        from .test_email_accounts import ConcurrentEmailAccountTests
        from estate_app.account_security import service, totp
        from estate_app.models import AccountAuthenticator
        user = User.objects.create_user('personal', password='Original-passphrase-472!')
        secret = 'JBSWY3DPEHPK3PXP'
        AccountAuthenticator.objects.create(user=user, secret=secret)
        code = code_for(secret, int(time.time()//30))
        def reset():
            if not totp.reset_password(User.objects.get(pk=user.pk), code,
                                       'New-passphrase-847!', 'New-passphrase-847!', lambda *args: False):
                raise service.AccountError('Code already consumed')
        self.assertEqual(ConcurrentEmailAccountTests.parallel(self, reset), ['rejected', 'success'])
