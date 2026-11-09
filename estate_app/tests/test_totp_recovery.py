from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(TOTP_RESET_SECRET='TESTSECRET')
class TotpRecoveryTests(TestCase):
    def setUp(self):
        self.url=reverse('totp-password-reset')
        self.user=get_user_model().objects.create_user('recovery-staff',password='Old-passphrase-289!',is_staff=True)
        self.data={'username':self.user.username,'code':'000000','password':'New-passphrase-739!','password_confirm':'New-passphrase-739!'}

    @patch('estate_app.views.auth._valid_totp',return_value=False)
    def test_limit_survives_new_sessions_and_addresses_and_blocks_valid_codes(self,valid):
        for n in range(5):
            self.assertEqual(Client().post(self.url,self.data,REMOTE_ADDR=f'10.0.0.{n+1}').status_code,200)
        valid.return_value=True
        response=Client().post(self.url,self.data,REMOTE_ADDR='100.64.0.1')
        self.assertEqual(response.status_code,429)
        self.assertGreater(int(response['Retry-After']),0)
        self.assertEqual(valid.call_count,5)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('Old-passphrase-289!'))

    @patch('estate_app.views.auth._valid_totp',return_value=False)
    def test_accounts_have_independent_budgets_and_unknown_names_are_generic(self,valid):
        get_user_model().objects.create_user('other-staff',is_staff=True)
        for n in range(6):Client().post(self.url,self.data)
        other=Client().post(self.url,{**self.data,'username':'other-staff'})
        unknown=Client().post(self.url,{**self.data,'username':'missing-staff'})
        self.assertEqual(other.status_code,200)
        self.assertContains(other,'The username or authenticator code is invalid.')
        self.assertContains(unknown,'The username or authenticator code is invalid.')
        for n in range(4):Client().post(self.url,{**self.data,'username':'missing-staff'})
        self.assertEqual(Client().post(self.url,{**self.data,'username':'missing-staff'}).status_code,429)

    @patch('estate_app.views.auth._valid_totp',return_value=False)
    @patch('estate_app.views.auth.time.time',return_value=2000000000)
    def test_window_expires_without_extending_on_blocked_requests(self,clock,valid):
        for n in range(5):Client().post(self.url,self.data)
        clock.return_value=2000000899
        response=Client().post(self.url,self.data)
        self.assertEqual(response.status_code,429);self.assertEqual(response['Retry-After'],'1')
        clock.return_value=2000000900
        self.assertEqual(Client().post(self.url,self.data).status_code,200)
        self.assertEqual(valid.call_count,6)

    @patch('estate_app.views.auth._valid_totp',return_value=True)
    @patch('estate_app.account_security.totp.matching_counter',return_value=66666666)
    def test_success_and_validation_keep_legacy_fallback_staff_only(self,counter,valid):
        from rest_framework.authtoken.models import Token
        token = Token.objects.create(user=self.user)
        client=Client()
        response=client.post(self.url,{**self.data,'password_confirm':'mismatch'})
        self.assertContains(response,'Passwords do not match.')
        response=client.post(self.url,self.data)
        self.assertRedirects(response,reverse('admin:login'))
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(self.data['password']))
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())
        ordinary=get_user_model().objects.create_user('ordinary',password='Existing-passphrase-291!')
        response=client.post(self.url,{**self.data,'username':ordinary.username})
        self.assertContains(response,'The username or authenticator code is invalid.')
        ordinary.refresh_from_db();self.assertTrue(ordinary.check_password('Existing-passphrase-291!'))

    def test_recovery_form_is_not_cached_and_has_accessible_return_link(self):
        response=self.client.get(self.url)
        self.assertIn('no-store',response['Cache-Control'])
        self.assertContains(response,'Back to BillTrack sign in')
        self.assertContains(response,'href="/"')
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url,self.data).status_code,403)

    def test_recovery_page_has_billtrack_identity_and_field_guidance(self):
        response=self.client.get(self.url)
        self.assertContains(response,'<title>Reset your password | BillTrack</title>',html=True)
        self.assertContains(response,'<main',count=1)
        self.assertContains(response,'id="code-help"')
        self.assertContains(response,'aria-describedby="code-help"')
        self.assertContains(response,'maxlength="6"')
        self.assertContains(response,'5 recovery attempts per account every 15 minutes')
        self.assertNotContains(response,'Django administration')

    @override_settings(TOTP_RESET_SECRET='')
    def test_personal_authenticator_recovery_does_not_require_emergency_secret(self):
        response=self.client.get(self.url)
        self.assertContains(response,'Set up your authenticator')
        self.assertContains(response,'Back to BillTrack sign in')
        self.assertContains(response,'<form')

    @patch('estate_app.views.auth._valid_totp',return_value=False)
    def test_error_is_visible_before_form_and_no_password_or_code_is_reflected(self,valid):
        response=self.client.post(self.url,self.data)
        body=response.content.decode()
        self.assertLess(body.index('role="alert"'),body.index('<form'))
        self.assertNotContains(response,'value="'+self.data['password']+'"')
        self.assertNotContains(response,'value="'+self.data['code']+'"')
