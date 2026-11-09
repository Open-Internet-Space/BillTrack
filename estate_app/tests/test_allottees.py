from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import Bill, Tenant
from ..serializers import TenantSerializer


class AllotteeBillingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('allottee-admin', 'admin@example.invalid', 'password')
        self.tenant = Tenant.objects.create(name='Billed allottee', type='Shop', gst_applicable=False)
        self.empty = Tenant.objects.create(name='Never billed allottee', type='Shop')
        Bill.objects.create(tenant=self.tenant, year=2026, month=1, rent=100)
        # Created later, but the billing period is older.
        Bill.objects.create(tenant=self.tenant, year=2025, month=12, rent=100)

    def test_latest_billing_period_and_empty_history_in_api(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get('/api/tenants/')
        self.assertEqual(response.status_code, 200)
        rows = {row['id']: row for row in response.data['results']}
        self.assertEqual(rows[self.tenant.pk]['last_billed_month'], 'January 2026')
        self.assertEqual(rows[self.empty.pk]['last_billed_month'], 'Never billed')

    def test_last_billed_month_has_no_per_allottee_queries(self):
        Tenant.objects.bulk_create([Tenant(name=f'Unbilled {index}', type='Office') for index in range(10)])
        with self.assertNumQueries(1):
            rows = TenantSerializer(Tenant.with_last_billed_month(), many=True).data
        self.assertEqual(len(rows), 12)

    def test_admin_lists_allottees_and_last_billed_month(self):
        self.client.force_login(self.user)
        response = self.client.get('/admin/estate_app/tenant/')
        self.assertContains(response, 'Allottees')
        self.assertContains(response, 'Last billed month')
        self.assertContains(response, 'January 2026')
        self.assertContains(response, 'Never billed')
        detail = self.client.get(f'/admin/estate_app/tenant/{self.tenant.pk}/change/')
        self.assertContains(detail, 'January 2026')
