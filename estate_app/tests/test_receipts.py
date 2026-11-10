import datetime
import importlib
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from rest_framework.test import APIClient

from ..models import Bill, Payment, Tenant
from ..views.bills import bill_read_queryset
from ..views.invoices import consolidated_invoice_context


class ReceiptBillingTests(TestCase):
    def setUp(self):
        from estate_app.models import SystemSettings
        SystemSettings.objects.update_or_create(pk=1, defaults={'letterhead_name':'Example Organisation'})
        self.tenant = Tenant.objects.create(
            name='Receipt Vendor', type='Shop', gst_applicable=False, due_days=7,
            penalty_type='percentage', custom_penalty_rate=Decimal('1'),
            custom_penalty_frequency='day',
        )
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(username='receipt-user'))

    def bill(self, **kwargs):
        return Bill.objects.create(tenant=self.tenant, month=1, year=2026,
                                   rent=Decimal('100'), **kwargs)

    def test_pending_receipt_has_no_overdue_or_penalty_even_after_tentative_date(self):
        bill = self.bill(due_date=timezone.localdate() - datetime.timedelta(days=30))
        self.assertEqual(bill.days_overdue, 0)
        self.assertEqual(bill.penalty, Decimal('0'))
        self.assertIsNone(bill.penalty_start_date)
        self.assertEqual(bill.penalty_calculation['result'], '0')
        Payment.objects.create(bill=bill, amount=Decimal('40'))
        bill.refresh_from_db()
        self.assertEqual(bill.balance_due, Decimal('60'))
        response = self.client.get('/api/bills/')
        row = response.data['results'][0]
        self.assertEqual(row['receipt_status'], 'Pending Receipt')
        self.assertEqual(row['status'], 'Partial')
        self.assertEqual(row['days_overdue'], 0)
        self.assertEqual(self.client.get('/api/dashboard/').data['total_outstanding'], 60)

    def test_five_days_exclude_receipt_day_and_cross_calendar_boundaries(self):
        for index, receipt in enumerate((datetime.date(2026, 11, 25), datetime.date(2026, 12, 29),
                                         datetime.date(2028, 2, 26)), 1):
            with self.subTest(receipt=receipt), patch('estate_app.models.billing.timezone.localdate', return_value=receipt):
                bill = Bill.objects.create(tenant=self.tenant, month=index, year=2026,
                                           rent=Decimal('100'), issue_date=receipt,
                                           due_date=receipt + datetime.timedelta(days=40))
                due = receipt + datetime.timedelta(days=5)
                self.assertEqual(bill.due_date, due)
                with patch('estate_app.models.billing.timezone.localdate', return_value=due):
                    self.assertEqual(bill.days_overdue, 0)
                    self.assertEqual(bill.penalty, Decimal('0'))
                with patch('estate_app.models.billing.timezone.localdate', return_value=due + datetime.timedelta(days=1)):
                    self.assertEqual(bill.days_overdue, 1)
                    self.assertEqual(bill.penalty, Decimal('1'))

    def test_api_confirmation_overrides_tentative_date_and_rejects_future_receipt(self):
        bill = self.bill(due_date=datetime.date(2026, 1, 1))
        today = timezone.localdate()
        response = self.client.patch(f'/api/bills/{bill.pk}/', {
            'issue_date': today.isoformat(), 'due_date': '2026-01-01', 'change_reason': 'Confirm actual receipt',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['due_date'], (today + datetime.timedelta(days=5)).isoformat())
        self.assertEqual(response.data['receipt_status'], 'Receipt Confirmed')
        response = self.client.patch(f'/api/bills/{bill.pk}/', {'due_date': '2026-01-01', 'change_reason': 'Check derived deadline'}, format='json')
        self.assertEqual(response.data['due_date'], (today + datetime.timedelta(days=5)).isoformat())
        response = self.client.patch(f'/api/bills/{bill.pk}/', {
            'issue_date': (today + datetime.timedelta(days=1)).isoformat(), 'change_reason': 'Invalid future receipt test',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        bill.refresh_from_db()
        self.assertEqual(bill.issue_date, today)

    def test_model_rejects_future_receipt(self):
        with self.assertRaises(ValidationError):
            self.bill(issue_date=timezone.localdate() + datetime.timedelta(days=1))

    def test_partial_and_early_payments_use_only_post_deadline_principal(self):
        today = timezone.localdate()
        bill = self.bill(issue_date=today - datetime.timedelta(days=15))
        Payment.objects.create(bill=bill, amount=Decimal('20'), payment_date=today - datetime.timedelta(days=12))
        Payment.objects.create(bill=bill, amount=Decimal('30'), payment_date=today - datetime.timedelta(days=5))
        Payment.objects.create(bill=bill, amount=Decimal('0'), penalty_paid=Decimal('1'), payment_date=today)
        bill.refresh_from_db()
        self.assertEqual(bill.penalty, Decimal('5.50'))
        annotated = bill_read_queryset().get(pk=bill.pk)
        self.assertEqual(annotated.penalty, bill.penalty)
        Payment.objects.create(bill=bill, amount=Decimal('50'), payment_date=today)
        bill.refresh_from_db()
        self.assertEqual(bill.penalty_accrued, Decimal('6.50'))
        bill.issue_date = today
        bill.save()
        bill.refresh_from_db()
        self.assertEqual(bill.penalty, Decimal('0'))
        self.assertEqual(bill.status, 'Paid')
        self.assertEqual(bill.payments.count(), 4)

    def test_pending_bills_are_excluded_from_previous_overdue_dues(self):
        self.bill(due_date=timezone.localdate() - datetime.timedelta(days=30))
        current = Bill.objects.create(tenant=self.tenant, month=2, year=2026, rent=Decimal('200'))
        self.assertEqual(current.previous_balance, Decimal('0'))
        self.assertEqual(consolidated_invoice_context([current])['previous_balance'], '0.00')

    def test_admin_uses_same_validation_and_deadline(self):
        from ..admin import BillAdminForm
        bill = self.bill(due_date=datetime.date(2026, 1, 1))
        data = {'tenant': self.tenant.pk, 'month': 1, 'year': 2026, 'rent': '100',
                'electric': '0', 'water': '0', 'gst_treatment': 'cgst_sgst',
                'due_date': '2026-01-01', 'issue_date': timezone.localdate().isoformat()}
        form = BillAdminForm(data=data, instance=bill)
        self.assertTrue(form.is_valid(), form.errors)
        bill = form.save()
        self.assertEqual(bill.due_date, timezone.localdate() + datetime.timedelta(days=5))
        data['issue_date'] = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        form = BillAdminForm(data=data, instance=bill)
        self.assertFalse(form.is_valid())
        self.assertIn('issue_date', form.errors)

    def test_legacy_confirmed_deadline_is_preserved_on_unrelated_edits(self):
        bill = self.bill(issue_date=datetime.date(2026, 10, 10))
        Bill.objects.filter(pk=bill.pk).update(due_date=datetime.date(2026, 10, 20))
        bill.refresh_from_db()
        bill.notes = 'Reference corrected'
        bill.due_date = datetime.date(2026, 1, 1)
        bill.save()
        bill.refresh_from_db()
        self.assertEqual(bill.due_date, datetime.date(2026, 10, 20))

    def test_bulk_creation_without_tentative_date_stays_pending(self):
        response = self.client.post('/api/bills/bulk-create/', {
            'tenant': self.tenant.pk, 'from_month': 1, 'from_year': 2026,
            'to_month': 2, 'to_year': 2026, 'rent': '100',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['created_count'], 2)
        for bill in response.data['created']:
            self.assertEqual(bill['receipt_status'], 'Pending Receipt')
            self.assertEqual(bill['days_overdue'], 0)

    def test_partial_save_does_not_apply_an_unsaved_receipt_change(self):
        bill = self.bill(issue_date=timezone.localdate() - datetime.timedelta(days=10))
        original_issue, original_due = bill.issue_date, bill.due_date
        bill.issue_date = timezone.localdate()
        bill.notes = 'Only save this note'
        bill.save(update_fields=['notes'])
        bill.refresh_from_db()
        self.assertEqual(bill.issue_date, original_issue)
        self.assertEqual(bill.due_date, original_due)
        self.assertEqual(bill.notes, 'Only save this note')
