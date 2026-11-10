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


class InvoicePrintSelectionTests(TestCase):
    def setUp(self):
        from estate_app.models import SystemSettings
        SystemSettings.objects.update_or_create(pk=1, defaults={'letterhead_name':'Example Organisation'})
        self.client.force_login(User.objects.create_user('print-reader', password='test-password'))
        tenant = Tenant.objects.create(name='Print Tenant', type='Shop', penalty_type='none')
        other = Tenant.objects.create(name='Other Print Tenant', type='Shop', penalty_type='none')
        self.first = Bill.objects.create(tenant=tenant, month=5, year=2026, rent=100,
                                        due_date=datetime.date(2026, 6, 1))
        self.second = Bill.objects.create(tenant=tenant, month=8, year=2026, rent=100,
                                         due_date=datetime.date(2026, 9, 1))
        self.other = Bill.objects.create(tenant=other, month=5, year=2026, rent=100,
                                        due_date=datetime.date(2026, 6, 1))

    def print_selected(self, *bills):
        return self.client.get('/api/invoice/bulk/', {'ids': ','.join(str(b.pk) for b in bills)}, HTTP_HOST='localhost')

    def test_both_individual_urls_use_format_2(self):
        for suffix in ('', 'format-2/'):
            response = self.client.get(f'/api/invoice/{self.first.pk}/{suffix}', HTTP_HOST='localhost')
            self.assertContains(response, 'Current Month Charges')
            self.assertNotContains(response, 'Consolidated Month-wise Charges')
            self.assertNotContains(response, 'Billed From')

    def test_single_selected_month_uses_format_2(self):
        response = self.print_selected(self.first)
        self.assertContains(response, 'Current Month Charges')
        self.assertNotContains(response, 'Consolidated Month-wise Charges')

    def test_repeated_bill_id_does_not_duplicate_charges_or_consolidate_one_month(self):
        response = self.print_selected(self.first, self.first)
        self.assertContains(response, 'Current Month Charges', count=1)
        self.assertNotContains(response, 'Consolidated Month-wise Charges')

    def test_multiple_months_are_consolidated_per_tenant(self):
        response = self.print_selected(self.first, self.second)
        self.assertContains(response, 'Consolidated Month-wise Charges', count=1)
        self.assertNotContains(response, 'Current Month Charges')
        response = self.print_selected(self.first, self.other, self.second)
        self.assertContains(response, 'Consolidated Month-wise Charges', count=1)
        self.assertContains(response, 'Current Month Charges', count=1)

    def test_admin_uses_the_same_single_and_multiple_month_selection(self):
        user = User.objects.create_superuser('print-admin', 'print@example.invalid', 'test-password')
        self.client.force_login(user)
        for bills, expected, excluded in (([self.first], 'Current Month Charges', 'Consolidated Month-wise Charges'),
                                           ([self.first, self.second], 'Consolidated Month-wise Charges', 'Current Month Charges')):
            response = self.client.get('/admin/estate_app/bill/bulk-print/',
                                      {'ids': ','.join(str(b.pk) for b in bills)}, HTTP_HOST='localhost')
            self.assertContains(response, expected)
            self.assertNotContains(response, excluded)

    def test_printed_reference_note_is_preserved_exactly(self):
        expected = ('Due date is 5 day from date of issue of this invoice. Penalty / interest, if applicable, '
                    'will be calculated as per the vendor billing profile. This invoice is computer-generated. '
                    'GST applicable on rent component only as per GST Act 2017.')
        for response in (self.print_selected(self.first), self.print_selected(self.first, self.second)):
            self.assertContains(response, expected)
            self.assertNotContains(response, '12% p.a.')
            self.assertNotContains(response, 'M/s Print Tenant')
