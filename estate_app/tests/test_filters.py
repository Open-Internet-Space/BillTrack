import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Bill, Payment, Tenant, UserProfile


class AdminFilterTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('filter-admin', 'filter@example.com', 'password'))
        self.shop = Tenant.objects.create(name='Alpha Shop', type='Shop', gst_applicable=False)
        self.canteen = Tenant.objects.create(name='Beta Canteen', type='Canteen', active=False, gst_applicable=False)
        self.pending = Bill.objects.create(tenant=self.shop, month=10, year=2026, rent=Decimal('100'), dispatch_ref_no='REF-PENDING')
        self.confirmed = Bill.objects.create(tenant=self.canteen, month=9, year=2026, rent=Decimal('100'),
                                              issue_date=datetime.date(2026, 10, 1), dispatch_ref_no='REF-CONFIRMED')
        Payment.objects.create(bill=self.pending, amount=Decimal('10'), receipt_no='PAY-ALPHA', payment_date=datetime.date(2026, 11, 1))
        Payment.objects.create(bill=self.confirmed, amount=Decimal('20'), receipt_no='PAY-BETA', payment_date=datetime.date(2026, 11, 5))

    def test_tenant_filters_combine_with_search_and_page_size(self):
        response = self.client.get(reverse('admin:estate_app_tenant_changelist'), {
            'type': 'Canteen', 'active__exact': '0', 'q': 'Beta', 'page_size': '15',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cl'].result_list), [self.canteen])
        self.assertContains(response, 'id="changelist-filter"')

    def test_bill_filters_include_receipt_type_period_and_dispatch_search(self):
        url = reverse('admin:estate_app_bill_changelist')
        response = self.client.get(url, {'receipt': 'pending', 'tenant__type': 'Shop', 'month': '10',
                                         'year': '2026', 'q': 'REF-PENDING', 'page_size': '15'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cl'].result_list), [self.pending])
        response = self.client.get(url, {'receipt': 'confirmed', 'q': 'REF-CONFIRMED'})
        self.assertEqual(list(response.context['cl'].result_list), [self.confirmed])

    def test_payment_filters_use_actual_dates_and_receipt_search(self):
        response = self.client.get(reverse('admin:estate_app_payment_changelist'), {
            'q': 'PAY-BETA', 'bill__tenant__type': 'Canteen',
            'payment_date__gte': '2026-11-05', 'payment_date__lte': '2026-11-05', 'page_size': '15',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p.receipt_no for p in response.context['cl'].result_list], ['PAY-BETA'])
        self.assertContains(response, 'id="changelist-filter"')

    def test_user_role_filter_preserves_existing_auth_filters(self):
        staff = User.objects.create_user('role-staff', is_staff=True)
        UserProfile.objects.create(user=staff, role='staff')
        response = self.client.get(reverse('admin:auth_user_changelist'), {'profile__role__exact': 'staff'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cl'].result_list), [staff])
        self.assertContains(response, 'By staff status')
