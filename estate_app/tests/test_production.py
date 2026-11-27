import json
import os
import subprocess
import sys
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from rest_framework.authtoken.models import Token

from ..models import Bill, SystemSettings, Tenant


class ProductionSettingsTests(TestCase):
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_shared_cursor_styles_reach_admin_and_recovery(self):
        for url in ('/admin/login/', '/admin/password-reset/totp/'):
            with self.subTest(url=url):
                response=self.client.get(url)
                self.assertContains(response, '/static/estate_app/cursor.css')
                self.assertContains(response, 'media="screen"')

    def load_settings(self, **values):
        env = {key: value for key, value in os.environ.items() if key not in (
            'DEBUG', 'SECRET_KEY', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS', 'BILLTRACK_TAILSCALE_IP', 'BILLTRACK_LAN_IP')}
        env.update(values)
        code = "from unittest.mock import patch; import json; patch('dotenv.load_dotenv').start(); from estate_project import settings as s; print(json.dumps({'debug': s.DEBUG, 'hosts': s.ALLOWED_HOSTS, 'origins': s.CSRF_TRUSTED_ORIGINS}))"
        return subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env)

    def test_production_is_default_and_requires_a_private_key(self):
        result = self.load_settings(SECRET_KEY='a-private-key-with-at-least-fifty-characters-0123456789')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['debug'])
        for value in ('', 'dev-only-estate-management-secret-key-change-in-production', 'short'):
            self.assertNotEqual(self.load_settings(SECRET_KEY=value).returncode, 0)

    def test_development_is_explicit_and_bad_configuration_is_rejected(self):
        self.assertEqual(self.load_settings(DEBUG='true').returncode, 0)
        key='a-private-key-with-at-least-fifty-characters-0123456789'
        for values in ({'DEBUG':'maybe'}, {'ALLOWED_HOSTS':'*'},
                       {'ALLOWED_HOSTS':'localhostTOTP_RESET_SECRET=not-a-host'},
                       {'BILLTRACK_TAILSCALE_IP':'10.0.0.1'}, {'BILLTRACK_LAN_IP':'8.8.8.8'},
                       {'CSRF_TRUSTED_ORIGINS':'http://localhost:8000/path'}):
            self.assertNotEqual(self.load_settings(SECRET_KEY=key, **values).returncode, 0)

    def test_tailnet_hosts_and_origins_are_exact(self):
        result=self.load_settings(SECRET_KEY='a-private-key-with-at-least-fifty-characters-0123456789', BILLTRACK_TAILSCALE_IP='100.64.0.10')
        self.assertEqual(result.returncode, 0, result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['hosts'], ['localhost', '127.0.0.1', '100.64.0.10'])
        self.assertIn('http://100.64.0.10:8000', data['origins'])
        self.assertNotIn('.ts.net', data['hosts'])

    def test_office_lan_is_included_as_an_exact_host(self):
        result=self.load_settings(SECRET_KEY='a-private-key-with-at-least-fifty-characters-0123456789', BILLTRACK_LAN_IP='10.0.0.10')
        self.assertEqual(result.returncode, 0, result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['hosts'], ['localhost','127.0.0.1','10.0.0.10'])
        self.assertIn('http://10.0.0.10:8000', data['origins'])

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['localhost'])
    def test_rejected_hosts_and_csrf_do_not_expose_debug_pages(self):
        response=Client().get('/', HTTP_HOST='untrusted.example')
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, 'Traceback', status_code=400)
        response=Client(enforce_csrf_checks=True).post('/admin/login/', {}, HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, 'Traceback', status_code=403)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['localhost'])
    @patch('django.views.generic.base.TemplateView.get', side_effect=RuntimeError('private-error-marker'))
    def test_server_errors_do_not_show_private_details(self, failure):
        response=Client(raise_request_exception=False).get('/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 500)
        self.assertNotContains(response, 'private-error-marker', status_code=500)
        self.assertNotContains(response, 'Traceback', status_code=500)


class InvoiceAccessTests(TestCase):
    def setUp(self):
        from estate_app.models import SystemSettings
        SystemSettings.objects.update_or_create(pk=1, defaults={'letterhead_name':'Example Organisation'})
        self.user=User.objects.create_user('invoice-reader', password='test-password')
        self.token=Token.objects.create(user=self.user)
        tenant=Tenant.objects.create(name='Invoice access check', type='Shop', gst_applicable=False)
        self.bill=Bill.objects.create(tenant=tenant, year=2026, month=1, rent=100)
        self.urls=[f'/api/invoice/{self.bill.pk}/', f'/api/invoice/{self.bill.pk}/format-2/',
                   f'/api/invoice/bulk/?ids={self.bill.pk}']

    def test_anonymous_html_and_pdf_requests_are_rejected(self):
        for url in self.urls:
            for output in ('', '&format=pdf' if '?' in url else '?format=pdf'):
                self.assertEqual(self.client.get(url+output).status_code, 401)

    def test_tokens_and_admin_sessions_can_print(self):
        for url in self.urls:
            response=self.client.get(url, HTTP_AUTHORIZATION='Token '+self.token.key)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.client.force_login(self.user)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200)

    @patch('estate_app.views.invoices.http.HTML')
    def test_pdf_and_inactive_account_access(self, html):
        html.return_value.write_pdf.return_value=b'%PDF-test'
        self.assertEqual(self.client.get(self.urls[0]+'?format=pdf', HTTP_AUTHORIZATION='Token '+self.token.key)['Content-Type'], 'application/pdf')
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.urls[0], HTTP_AUTHORIZATION='Token '+self.token.key).status_code, 401)


class CommunicationSwitchTests(TestCase):
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_signup_and_email_switches_are_independent(self):
        from django.core.exceptions import ValidationError
        from ..reminders.service import send_reminders, send_test

        config = SystemSettings.get_settings()
        config.new_signups_enabled = False
        config.bill_email_enabled = False
        config.save()
        with patch('estate_app.account_security.views.service.available', return_value=True):
            response = self.client.post('/accounts/signup/', {
                'name': 'Closed signup', 'email': 'closed@example.invalid', 'password': 'Temporary123!'
            })
            self.assertContains(response, 'New signups are currently closed')
            self.assertFalse(User.objects.filter(email='closed@example.invalid').exists())
            self.assertContains(self.client.get('/accounts/password-reset/'), 'Send email code')
        self.assertNotContains(self.client.get('/admin/login/'), '>Create account</a>')

        user = User.objects.create_superuser('communication-admin')
        self.client.force_login(user)
        self.assertContains(self.client.get('/admin/email-reminders/'), 'Bills email communication is disabled')
        with self.assertRaisesMessage(ValidationError, 'Bills email communication is disabled'):
            send_reminders(confirmed=[{}], user_id=user.pk)
        with self.assertRaisesMessage(ValidationError, 'Bills email communication is disabled'):
            send_test('test@example.invalid')
        auth = {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=user).key}'}
        self.assertEqual(self.client.get('/api/email-templates/', **auth).status_code, 200)
        config.bill_email_copy_enabled = False
        config.save()
        self.assertEqual(self.client.get('/api/email-templates/', **auth).status_code, 403)
        self.assertEqual(self.client.post('/api/email-drafts/generate/', {}, **auth).status_code, 403)
