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


class BillPreviousDuesTests(TestCase):
    def setUp(self):
        from estate_app.models import SystemSettings
        SystemSettings.objects.update_or_create(pk=1, defaults={'letterhead_name':'Example Organisation'})
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            type='Shop',
            gst_applicable=False,
            penalty_type='none',
        )

    def test_total_payable_includes_older_overdue_balance(self):
        today = timezone.localdate()
        old_bill = Bill.objects.create(
            invoice_no='TEST/OLD/001',
            tenant=self.tenant,
            month=1,
            year=today.year,
            rent=Decimal('100.00'),
            issue_date=today - datetime.timedelta(days=6),
            due_date=today - datetime.timedelta(days=1),
        )
        Payment.objects.create(bill=old_bill, amount=Decimal('30.00'))

        current_bill = Bill.objects.create(
            invoice_no='TEST/CUR/001',
            tenant=self.tenant,
            month=2,
            year=today.year,
            rent=Decimal('200.00'),
            due_date=today + datetime.timedelta(days=7),
        )

        self.assertEqual(current_bill.previous_balance, Decimal('70.00'))
        self.assertEqual(current_bill.total_payable, Decimal('270.00'))

    def test_custom_penalty_rate_selects_percentage_type(self):
        serializer = TenantSerializer(data={
            'name': 'Custom Penalty Tenant', 'type': 'Shop',
            'penalty_type': 'system', 'custom_penalty_rate': '1.00',
            'custom_penalty_frequency': 'day',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        tenant = serializer.save()

        self.assertEqual(tenant.penalty_type, 'percentage')
        self.assertEqual(tenant.get_penalty_config()['rate'], Decimal('1.00'))
        self.assertEqual(tenant.get_penalty_config()['frequency'], 'day')

    def test_payment_exposes_bill_fields_for_register_filters(self):
        bill = Bill.objects.create(
            tenant=self.tenant, month=6, year=2026,
            rent=Decimal('100.00'), due_date=timezone.localdate(),
        )
        payment = Payment.objects.create(bill=bill, amount=Decimal('25.00'))

        data = PaymentSerializer(payment).data

        self.assertEqual(data['bill_tenant'], self.tenant.pk)
        self.assertEqual(data['bill_year'], 2026)
        self.assertEqual(data['bill_month'], 6)

    def test_future_due_previous_bill_is_not_included(self):
        today = timezone.localdate()
        Bill.objects.create(
            invoice_no='TEST/FUT/001',
            tenant=self.tenant,
            month=1,
            year=today.year,
            rent=Decimal('100.00'),
            due_date=today + datetime.timedelta(days=1),
        )
        current_bill = Bill.objects.create(
            invoice_no='TEST/CUR/002',
            tenant=self.tenant,
            month=2,
            year=today.year,
            rent=Decimal('200.00'),
            due_date=today + datetime.timedelta(days=7),
        )

        self.assertEqual(current_bill.previous_balance, Decimal('0'))
        self.assertEqual(current_bill.total_payable, Decimal('200.00'))

    def test_invoice_number_is_auto_generated(self):
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant,
            month=1,
            year=today.year,
            rent=Decimal('100.00'),
            due_date=today + datetime.timedelta(days=7),
        )

        self.assertEqual(bill.invoice_no, f'Jan/{today.year}/001')

    def test_invoice_autonumber_increments_within_month(self):
        today = timezone.localdate()
        other_tenant = Tenant.objects.create(
            name='Other Tenant',
            type='Shop',
            gst_applicable=False,
            penalty_type='none',
        )
        first_bill = Bill.objects.create(
            tenant=self.tenant,
            month=2,
            year=today.year,
            rent=Decimal('100.00'),
            due_date=today + datetime.timedelta(days=7),
        )
        second_bill = Bill.objects.create(
            tenant=other_tenant,
            month=2,
            year=today.year,
            rent=Decimal('200.00'),
            due_date=today + datetime.timedelta(days=7),
        )

        self.assertEqual(first_bill.invoice_no, f'Feb/{today.year}/001')
        self.assertEqual(second_bill.invoice_no, f'Feb/{today.year}/002')

    def test_bulk_create_uses_same_due_date_for_all_months(self):
        user = User.objects.create_user(username='billing-user', password='password')
        client = APIClient()
        client.force_authenticate(user=user)
        due_date = datetime.date(2026, 5, 15)

        response = client.post(
            '/api/bills/bulk-create/',
            data={
                'tenant': self.tenant.id,
                'from_month': 1,
                'from_year': 2026,
                'to_month': 2,
                'to_year': 2026,
                'rent': '100.00',
                'water': '0',
                'gst_treatment': 'cgst_sgst',
                'due_date': due_date.isoformat(),
            },
            format='json',
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Bill.objects.get(month=1, year=2026).due_date, due_date)
        self.assertEqual(Bill.objects.get(month=2, year=2026).due_date, due_date)

    def test_tenant_gstin_is_normalized(self):
        self.tenant.gstin = 'test-gstin'
        self.tenant.email = ' billing@example.com '
        self.tenant.save()

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.gstin, 'TEST-GSTIN')
        self.assertEqual(self.tenant.email, 'billing@example.com')

    def test_due_date_is_five_days_after_receipt_despite_legacy_tenant_due_days(self):
        self.tenant.due_days = 7
        self.tenant.save()
        issue_date = datetime.date(2026, 5, 8)

        bill = Bill.objects.create(
            tenant=self.tenant,
            month=5,
            year=2026,
            rent=Decimal('100.00'),
            issue_date=issue_date,
        )

        self.assertEqual(bill.due_date, issue_date + datetime.timedelta(days=5))

    def test_percentage_penalty_uses_configured_frequency_after_due_date(self):
        self.tenant.penalty_type = 'percentage'
        self.tenant.custom_penalty_rate = Decimal('1.00')
        self.tenant.custom_penalty_frequency = 'day'
        self.tenant.save()
        today = timezone.localdate()

        bill = Bill.objects.create(
            tenant=self.tenant,
            month=5,
            year=today.year,
            rent=Decimal('100.00'),
            issue_date=today - datetime.timedelta(days=7),
        )

        self.assertEqual(bill.penalty, Decimal('2.00'))

    def test_lumpsum_penalty_uses_configured_frequency_after_due_date(self):
        self.tenant.penalty_type = 'lumpsum'
        self.tenant.custom_penalty_lumpsum = Decimal('10.00')
        self.tenant.custom_penalty_frequency = 'day'
        self.tenant.save()
        today = timezone.localdate()

        bill = Bill.objects.create(
            tenant=self.tenant,
            month=5,
            year=today.year,
            rent=Decimal('100.00'),
            issue_date=today - datetime.timedelta(days=8),
        )

        self.assertEqual(bill.penalty, Decimal('30.00'))

    def test_partial_payments_keep_penalty_from_each_unpaid_period(self):
        self.tenant.penalty_type = 'percentage'
        self.tenant.custom_penalty_rate = Decimal('1.00')
        self.tenant.custom_penalty_frequency = 'day'
        self.tenant.save()
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant, month=6, year=today.year,
            rent=Decimal('100.00'), issue_date=today - datetime.timedelta(days=20),
        )
        Payment.objects.create(bill=bill, amount=Decimal('50.00'), payment_date=today - datetime.timedelta(days=10))
        self.assertEqual(bill.penalty_calculation['result'], '10.00')
        Payment.objects.create(bill=bill, amount=Decimal('50.00'), payment_date=today)
        bill.refresh_from_db()

        self.assertEqual(bill.penalty, Decimal('10.00'))
        self.tenant.custom_penalty_rate = Decimal('2.00')
        self.tenant.save()
        bill.refresh_from_db()
        self.assertEqual(bill.penalty, Decimal('10.00'))

    def test_deleting_settlement_payment_recalculates_penalty(self):
        self.tenant.penalty_type = 'percentage'
        self.tenant.custom_penalty_rate = Decimal('1.00')
        self.tenant.custom_penalty_frequency = 'day'
        self.tenant.save()
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant, month=7, year=today.year,
            rent=Decimal('100.00'), issue_date=today - datetime.timedelta(days=20),
        )
        first = Payment.objects.create(bill=bill, amount=Decimal('100.00'), payment_date=today - datetime.timedelta(days=10))
        Payment.objects.create(bill=bill, amount=Decimal('100.00'), payment_date=today)
        user = User.objects.create_user(username='payment-admin', password='password')
        UserProfile.objects.create(user=user, role='admin')
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.delete(f'/api/payments/{first.pk}/', HTTP_HOST='localhost')
        bill.refresh_from_db()

        self.assertEqual(response.status_code, 204)
        self.assertEqual(bill.penalty_accrued, Decimal('15.00'))
        self.assertEqual(bill.penalty_accrued_on, today)
        self.assertEqual(bill.status, 'Partial')

    def test_moving_payment_recalculates_original_bill(self):
        today = timezone.localdate()
        original = Bill.objects.create(tenant=self.tenant, month=12, year=today.year, rent=Decimal('100.00'), due_date=today)
        replacement = Bill.objects.create(tenant=self.tenant, month=1, year=today.year + 1, rent=Decimal('100.00'), due_date=today)
        payment = Payment.objects.create(bill=original, amount=Decimal('100.00'))
        user = User.objects.create_user(username='move-payment-user', password='password')
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.patch(f'/api/payments/{payment.pk}/', {'bill': replacement.pk}, format='json', HTTP_HOST='localhost')
        original.refresh_from_db()
        replacement.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(original.status, 'Unpaid')
        self.assertEqual(replacement.status, 'Paid')

    def test_penalty_only_payment_is_valid(self):
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant, month=9, year=today.year,
            rent=Decimal('100.00'), due_date=today + datetime.timedelta(days=7),
        )
        payment = Payment(bill=bill, amount=Decimal('0.00'), penalty_paid=Decimal('10.00'))

        payment.full_clean()

    def test_api_rejects_empty_payment(self):
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant, month=10, year=today.year,
            rent=Decimal('100.00'), due_date=today + datetime.timedelta(days=7),
        )
        user = User.objects.create_user(username='payment-user', password='password')
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post('/api/payments/', {
            'bill': bill.pk, 'amount': '0.00', 'penalty_paid': '0.00',
            'payment_date': today.isoformat(),
        }, format='json', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 400)

    def test_consolidated_invoice_includes_electric_reading(self):
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant,
            month=5,
            year=2026,
            rent=Decimal('0.00'),
            electric=Decimal('436.82'),
            electric_reading='220',
            due_date=today + datetime.timedelta(days=7),
        )

        context = consolidated_invoice_context([bill])

        self.assertEqual(context['line_items'][0]['electric_reading'], '220')

    def test_consolidated_invoice_keeps_penalty_payment_out_of_principal_balance(self):
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant, month=8, year=today.year,
            rent=Decimal('100.00'), due_date=today + datetime.timedelta(days=7),
        )
        Payment.objects.create(bill=bill, amount=Decimal('50.00'), penalty_paid=Decimal('10.00'))

        context = consolidated_invoice_context([bill])

        self.assertEqual(context['balance_due'], '50.00')
        self.assertEqual(context['excess_paid'], '0.00')
        self.assertEqual(context['total_payable'], '50.00')

    def test_bulk_invoice_shows_principal_overpayment_credit(self):
        today = timezone.localdate()
        bill = Bill.objects.create(
            tenant=self.tenant, month=11, year=today.year,
            rent=Decimal('100.00'), due_date=today + datetime.timedelta(days=7),
        )
        Payment.objects.create(bill=bill, amount=Decimal('110.00'))
        context = {'print_invoices': [{'invoice': invoice_context(bill), 'consolidated': False}]}

        for template in ('bulk_invoice.html', 'admin/estate_app/bill/bulk_print.html'):
            with self.subTest(template=template):
                html = render_to_string(template, context)
                self.assertIn('Excess Paid / Credit', html)
                self.assertTrue('Rs. 10.00' in html)

    def test_consolidated_invoice_includes_unselected_overdue_gap_bill(self):
        today = timezone.localdate()
        year = today.year if today.month > 4 else today.year - 1
        first_selected = Bill.objects.create(
            tenant=self.tenant,
            month=1,
            year=year,
            rent=Decimal('100.00'),
            issue_date=today - datetime.timedelta(days=8),
            due_date=today - datetime.timedelta(days=3),
        )
        Bill.objects.create(
            tenant=self.tenant,
            month=2,
            year=year,
            rent=Decimal('50.00'),
            issue_date=today - datetime.timedelta(days=7),
            due_date=today - datetime.timedelta(days=2),
        )
        last_selected = Bill.objects.create(
            tenant=self.tenant,
            month=3,
            year=year,
            rent=Decimal('200.00'),
            issue_date=today - datetime.timedelta(days=6),
            due_date=today - datetime.timedelta(days=1),
        )

        context = consolidated_invoice_context([first_selected, last_selected])

        self.assertEqual(context['previous_balance'], '50.00')

    def test_bill_delete_endpoint_removes_bill(self):
        user = User.objects.create_user(username='delete-user', password='password')
        client = APIClient()
        client.force_authenticate(user=user)
        bill = Bill.objects.create(
            tenant=self.tenant,
            month=6,
            year=2026,
            rent=Decimal('100.00'),
            due_date=timezone.localdate() + datetime.timedelta(days=7),
        )

        response = client.delete(f'/api/bills/{bill.id}/', HTTP_HOST='localhost')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Bill.objects.filter(pk=bill.pk).exists())
