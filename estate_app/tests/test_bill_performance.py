import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.template.loader import render_to_string
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework.test import APIClient
from ..models import Bill, Payment, Tenant, UserProfile, SystemSettings
from ..serializers import PaymentSerializer, TenantSerializer
from ..views import consolidated_invoice_context, invoice_context


class BillReadPerformanceTests(TestCase):
    def setUp(self):
        from estate_app.models import SystemSettings
        SystemSettings.objects.update_or_create(pk=1, defaults={'letterhead_name':'Example Organisation'})
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(username='performance-test'))
        self.settings = SystemSettings.get_settings()
        self.tenant = Tenant.objects.create(name='Performance Tenant', type='Shop', gst_applicable=False)
        today = timezone.localdate()
        for month in range(1, 9):
            Bill.objects.create(tenant=self.tenant, invoice_no=f'PERF/{month}', month=month, year=today.year,
                                rent=Decimal('100.00'), issue_date=today - datetime.timedelta(days=15))

    def test_bill_list_queries_do_not_grow_per_bill(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/bills/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 8)
        self.assertEqual(response.data['results'][0]['balance_due'], '100.00')
        self.assertLessEqual(len(queries), 6)

    def test_dashboard_reads_payments_in_bulk(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_outstanding'], 800.0)
        self.assertLessEqual(len(queries), 8)

    def test_settings_changes_are_visible_on_the_next_request(self):
        self.settings.penalty_rate_pa = Decimal('12.00')
        self.settings.save()
        before = self.client.get('/api/bills/').data['results'][0]['penalty']
        self.settings.penalty_rate_pa = Decimal('24.00')
        self.settings.save()
        after = self.client.get('/api/bills/').data['results'][0]['penalty']
        self.assertGreater(Decimal(after), Decimal(before))
