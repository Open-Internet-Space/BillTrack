from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from .test_account_authenticator import code_for


@override_settings(TOTP_RESET_SECRET='JBSWY3DPEHPK3PXP')
@patch('time.time', return_value=2000000000)
class EmergencyRecoveryTests(TestCase):
    password = 'Office-passphrase-842!'

    def setUp(self):
        self.boss = User.objects.create_superuser('boss', 'boss@example.org', self.password)
        self.user = User.objects.create_user('ordinary', 'ordinary@example.org', self.password)

    def test_emergency_recovers_ordinary_account_with_personal_totp_and_revokes_token(self, clock):
        from estate_app.models import AccountAuthenticator
        AccountAuthenticator.objects.create(user=self.user, secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ')
        token = Token.objects.create(user=self.user)
        response = self.client.post(reverse('totp-password-reset'), {
            'username': self.user.email, 'recovery_method': 'emergency', 'code': code_for('JBSWY3DPEHPK3PXP'),
            'password': self.password+'new', 'password_confirm': self.password+'new',
        })
        self.assertContains(response, 'Password updated')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password+'new'))
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_same_emergency_code_cannot_be_reused_for_another_account(self, clock):
        url = reverse('totp-password-reset')
        data = {'recovery_method': 'emergency', 'code': code_for('JBSWY3DPEHPK3PXP'),
                'password': self.password+'new', 'password_confirm': self.password+'new'}
        self.client.post(url, {**data, 'username': self.user.username})
        response = self.client.post(url, {**data, 'username': self.boss.username})
        self.assertContains(response, 'invalid')
        self.boss.refresh_from_db()
        self.assertTrue(self.boss.check_password(self.password))

    def test_emergency_qr_requires_superuser_and_fresh_password(self, clock):
        url = reverse('admin-emergency-authenticator')
        staff = User.objects.create_user('staff', password=self.password, is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.boss)
        response = self.client.get(url)
        self.assertNotContains(response, 'data:image/svg+xml;base64,')
        self.assertNotContains(response, 'JBSWY3DPEHPK3PXP')
        response = self.client.post(url, {'password': 'wrong'})
        self.assertNotContains(response, 'JBSWY3DPEHPK3PXP')
        response = self.client.post(url, {'password': self.password})
        self.assertContains(response, 'data:image/svg+xml;base64,')
        self.assertContains(response, 'Superuser emergency')
        self.assertIn('no-store', response['Cache-Control'])

    def test_personal_enrollment_shows_locally_generated_qr(self, clock):
        response = self.client.post(reverse('account-authenticator'), {
            'username': self.user.username, 'password': self.password})
        self.assertContains(response, 'data:image/svg+xml;base64,')
        self.assertContains(response, 'Scan')

    def test_admin_password_screens_link_to_recovery_tools(self, clock):
        self.client.force_login(self.boss)
        for url in [reverse('admin:password_change'), reverse('admin:auth_user_password_change', args=[self.boss.pk])]:
            response = self.client.get(url)
            self.assertContains(response, reverse('account-authenticator'))
            self.assertContains(response, reverse('admin-emergency-authenticator'))

    def test_emergency_does_not_approve_or_enable_an_account(self, clock):
        from estate_app.models import AccountAccess
        AccountAccess.objects.create(user=self.user, status='pending')
        response = self.client.post(reverse('totp-password-reset'), {
            'username': self.user.username, 'recovery_method': 'emergency', 'code': code_for('JBSWY3DPEHPK3PXP'),
            'password': self.password+'new', 'password_confirm': self.password+'new'})
        self.assertContains(response, 'invalid')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertContains(self.client.post(reverse('totp-password-reset'), {
            'username': self.user.username, 'recovery_method': 'emergency', 'code': code_for('JBSWY3DPEHPK3PXP'),
            'password': self.password+'new', 'password_confirm': self.password+'new'}), 'invalid')

    def test_emergency_throttle_is_visible_for_known_and_unknown_accounts(self, clock):
        from estate_app.account_security import service
        for _ in range(20):
            service.limit('superuser-emergency', 'installation', 20, 900)
        for username in [self.user.username, 'unknown']:
            response = self.client.post(reverse('totp-password-reset'), {'username': username, 'recovery_method': 'emergency'})
            self.assertContains(response, 'Too many emergency recovery attempts', status_code=429)
            self.assertEqual(response['Retry-After'], '900')

    def test_emergency_qr_enforces_csrf_without_disclosing_key(self, clock):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.boss)
        response = client.post(reverse('admin-emergency-authenticator'), {'password': self.password})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b'JBSWY3DPEHPK3PXP', response.content)


class AuthenticatorQRTests(SimpleTestCase):
    def test_uri_and_svg_are_local_and_use_standard_authenticator_parameters(self):
        import base64
        from urllib.parse import urlparse, parse_qs, unquote
        from xml.etree import ElementTree
        from estate_app.account_security.qr import authenticator_uri, qr_data_uri
        secret = 'JBSWY3DPEHPK3PXP'
        uri = urlparse(authenticator_uri(secret, 'name+office@example.org'))
        self.assertEqual((uri.scheme, uri.netloc), ('otpauth', 'totp'))
        self.assertEqual(unquote(uri.path), '/BillTrack:name+office@example.org')
        self.assertEqual(parse_qs(uri.query), {'secret':[secret], 'issuer':['BillTrack'],
                                              'algorithm':['SHA1'], 'digits':['6'], 'period':['30']})
        data = qr_data_uri(secret, 'Test account').split(',', 1)[1]
        svg = ElementTree.fromstring(base64.b64decode(data))
        self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertGreater(len(list(svg.iter('{http://www.w3.org/2000/svg}rect'))), 20)
        self.assertEqual(list(svg.iter('{http://www.w3.org/2000/svg}script')), [])


class ConcurrentEmergencyRecoveryTests(TransactionTestCase):
    @override_settings(TOTP_RESET_SECRET='JBSWY3DPEHPK3PXP')
    def test_emergency_code_is_single_use_across_concurrent_different_accounts(self):
        import time
        from queue import SimpleQueue
        from .test_email_accounts import ConcurrentEmailAccountTests
        from estate_app.account_security import service, totp
        users = SimpleQueue()
        for name in ['one', 'two']:
            users.put(User.objects.create_user(name, password='Original-passphrase-472!').pk)
        code = code_for('JBSWY3DPEHPK3PXP', int(time.time()//30))
        def reset():
            if not totp.reset_password(User.objects.get(pk=users.get()), code, 'New-passphrase-847!',
                                       'New-passphrase-847!', lambda *args: True, emergency=True):
                raise service.AccountError('Code already consumed')
        self.assertEqual(ConcurrentEmailAccountTests.parallel(self, reset), ['rejected', 'success'])
