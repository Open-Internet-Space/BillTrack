import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from estate_app.models import ActivityEntry, Allotment, Bill, RentRevision, Shop, SystemSettings, Tenant
from estate_app.tests.transaction_case import ActivityTransactionTestCase


class EstateBillingTests(TestCase):
    def setUp(self):
        self.assertTrue(hasattr(Bill, 'allotment'), 'Bills are not linked to allotment terms yet')
        self.tenant = Tenant.objects.create(name='Multi-shop billing test', type='Shop', gst_applicable=False, penalty_type='none')
        self.terms = []
        for code in ('A-101', 'N-401'):
            shop = Shop.objects.create(code=code, name=code, category='utility')
            self.terms.append(Allotment.objects.create(shop=shop, tenant=self.tenant, source_notice='368/2025',
                award_reference=f'Award {code}', letter_issued_on=dt.date(2026, 1, 1),
                start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 12, 31),
                actual_area=150, measurement_reference='Synthetic measurement'))
            RentRevision.objects.create(original_award=self.terms[-1], effective_date=dt.date(2026, 1, 1),
                rate=Decimal('20'), approval_reference='Synthetic accepted rate', reason='Reviewed synthetic rate baseline')
        self.api = APIClient()
        self.api.force_authenticate(User.objects.create_user('estate-billing-tester'))

    def bill(self, term, **changes):
        values = dict(tenant=self.tenant, allotment=term, billing_category='allotment',
                      year=2026, month=6, full_month_rent=Decimal('100'))
        values.update(changes)
        return Bill.objects.create(**values)

    def test_independent_same_month_bills_and_duplicate_constraint(self):
        first = self.bill(self.terms[0])
        second = self.bill(self.terms[1])
        self.assertNotEqual(first.invoice_no, second.invoice_no)
        with self.assertRaises((ValidationError, IntegrityError)):
            self.bill(self.terms[0])
        self.assertEqual(Bill.objects.count(), 2)

    def test_owner_and_billing_period_must_match_the_term(self):
        other = Tenant.objects.create(name='Different person', type='Shop')
        for changes in [dict(tenant=other), dict(year=2027), dict(billing_category='other'), dict(allotment=None)]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.bill(self.terms[0], **changes)

    def test_carry_forward_stays_in_its_term_and_legacy_is_separate(self):
        self.bill(self.terms[0], month=1, full_month_rent=Decimal('100'), issue_date=dt.date(2026, 1, 1))
        self.bill(self.terms[1], month=1, full_month_rent=Decimal('200'), issue_date=dt.date(2026, 1, 1))
        Bill.objects.create(tenant=self.tenant, month=1, year=2026, rent=Decimal('300'), issue_date=dt.date(2026, 1, 1))
        current = self.bill(self.terms[0], month=2)
        self.assertEqual(current.previous_balance, Decimal('100'))
        legacy = Bill.objects.create(tenant=self.tenant, month=2, year=2026, rent=Decimal('10'))
        self.assertEqual(legacy.previous_balance, Decimal('300'))

    def test_api_requires_a_term_or_explicit_other_charge_category(self):
        payload = {'tenant': self.tenant.pk, 'month': 6, 'year': 2026, 'full_month_rent': '3000'}
        self.assertEqual(self.api.post('/api/bills/', payload, format='json').status_code, 400)
        response = self.api.post('/api/bills/', {**payload, 'allotment': self.terms[0].pk,
            'holiday_start_date': '2026-06-10', 'holiday_end_date': '2026-06-19', 'rent': '1.00'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['rent'], '2000.00')
        self.assertEqual(response.data['shop_code'], 'A-101')
        response = self.api.post('/api/bills/', {**payload, 'billing_category': 'other',
            'notes': 'Reviewed non-shop monthly charge'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_bill_link_cannot_be_moved_by_an_ordinary_edit(self):
        bill = self.bill(self.terms[0])
        response = self.api.patch(f'/api/bills/{bill.pk}/', {'allotment': self.terms[1].pk,
            'change_reason': 'Attempt reassignment'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.terms[0].tenant = Tenant.objects.create(name='Replacement occupant', type='Shop')
        with self.assertRaises(ValidationError):
            self.terms[0].save()
        shop = self.terms[0].shop
        shop.code = 'CHANGED-CODE'
        with self.assertRaises(ValidationError):
            shop.save()

    def range_payload(self, **changes):
        values = dict(tenant=self.tenant.pk, allotment=self.terms[0].pk, full_month_rent='3100',
            rent_override_reason='Reviewed synthetic monthly amount for waiver example',
            from_month=1, from_year=2026, to_month=2, to_year=2026,
            holiday_start_date='2026-01-20', holiday_end_date='2026-02-10', water='50',
            month_items=[{'year': 2026, 'month': 1, 'electric': '100'},
                         {'year': 2026, 'month': 2, 'electric': '200'}])
        return {**values, **changes}

    def test_preview_is_read_only_and_matches_range_save(self):
        before = (Bill.objects.count(), SystemSettings.objects.count(), ActivityEntry.objects.count())
        response = self.api.post('/api/bills/preview/', self.range_payload(), format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(before, (Bill.objects.count(), SystemSettings.objects.count(), ActivityEntry.objects.count()))
        rows = response.data['months']
        self.assertEqual([row['rent'] for row in rows], ['1900.00', '1992.86'])
        self.assertEqual([row['holiday_closed_days'] for row in rows], [12, 10])
        self.assertEqual([row['total_amount'] for row in rows], ['2050.00', '2242.86'])
        saved = self.api.post('/api/bills/bulk-create/', self.range_payload(), format='json')
        self.assertEqual(saved.status_code, 201, saved.data)
        self.assertEqual([row['rent'] for row in saved.data['created']], [row['rent'] for row in rows])
        for bill in Bill.objects.all():
            self.assertEqual(bill.full_month_rent, Decimal('3100'))
            self.assertEqual(bill.allotment_id, self.terms[0].pk)

    def test_bulk_duplicates_are_scoped_to_term(self):
        self.bill(self.terms[1], month=1)
        self.bill(self.terms[0], month=2)
        response = self.api.post('/api/bills/bulk-create/', self.range_payload(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['created_count'], 1)
        self.assertEqual(response.data['skipped_count'], 1)
        self.assertTrue(Bill.objects.filter(allotment=self.terms[0], month=1).exists())

    def test_invalid_range_or_electric_rows_never_save_partial_bills(self):
        for changes in [dict(to_year=2027), dict(from_month=13), dict(to_year=2101),
                        dict(holiday_start_date='2025-01-01', holiday_end_date='2025-01-10'),
                        dict(month_items=[{'year': 2026, 'month': 2, 'electric': '-1'}]),
                        dict(month_items=[{'year': 2026, 'month': 1}, {'year': 2026, 'month': 1}]),
                        dict(month_items=[{'year': 2026, 'month': 3}]), dict(month_items='invalid')]:
            with self.subTest(changes=changes):
                for endpoint in ('preview', 'bulk-create'):
                    response = self.api.post(f'/api/bills/{endpoint}/', self.range_payload(**changes), format='json')
                    self.assertEqual(response.status_code, 400, response.data)
                self.assertFalse(Bill.objects.exists())

    def test_admin_bill_forms_use_the_same_waiver_and_assignment_rules(self):
        from django.forms.models import model_to_dict
        from estate_app.admin import BillAdminForm
        bill = self.bill(self.terms[0], full_month_rent=Decimal('3000'))
        data = {**model_to_dict(bill), 'holiday_start_date': '2026-06-10', 'holiday_end_date': '2026-06-19'}
        form = BillAdminForm(data=data, instance=bill)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.rent, Decimal('2000'))
        data['allotment'] = self.terms[1].pk
        form = BillAdminForm(data=data, instance=saved)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().allotment_id, self.terms[0].pk)

    def test_admin_bulk_bill_is_atomic_and_linked(self):
        admin = User.objects.create_superuser('estate-finance-admin', password='test')
        self.client.force_login(admin)
        payload = {**self.range_payload(), 'from_period': '2026-01', 'to_period': '2026-02',
                   'due_date': '2026-03-01', 'electric_2026-01': '100', 'electric_2026-02': '-1'}
        response = self.client.post('/admin/estate_app/bill/bulk-add/', payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Bill.objects.exists())
        payload['electric_2026-02'] = '200'
        response = self.client.post('/admin/estate_app/bill/bulk-add/', payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(Bill.objects.order_by('month').values_list('rent', flat=True)),
                         [Decimal('1900'), Decimal('1992.86')])
        self.assertEqual(Bill.objects.filter(allotment=self.terms[0]).count(), 2)

    def test_admin_bulk_requires_bill_add_permission(self):
        staff = User.objects.create_user('unprivileged-estate-staff', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post('/admin/estate_app/bill/bulk-add/', {
            **self.range_payload(), 'from_period': '2026-01', 'to_period': '2026-02'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Bill.objects.exists())

    def test_edit_preview_and_save_recalculate_from_original_base(self):
        bill = self.bill(self.terms[0], full_month_rent=Decimal('3000'),
                         holiday_start_date=dt.date(2026, 6, 10), holiday_end_date=dt.date(2026, 6, 19))
        data = {'holiday_end_date': '2026-06-24'}
        count = ActivityEntry.objects.count()
        response = self.api.post(f'/api/bills/{bill.pk}/preview/', data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['months'][0]['rent'], '1500.00')
        bill.refresh_from_db()
        self.assertEqual(bill.rent, Decimal('2000'))
        self.assertEqual(ActivityEntry.objects.count(), count)
        response = self.api.patch(f'/api/bills/{bill.pk}/', {**data, 'change_reason': 'Correct recorded closure'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['rent'], '1500.00')
        response = self.api.patch(f'/api/bills/{bill.pk}/', {'full_month_rent': None,
            'holiday_start_date': None, 'holiday_end_date': None, 'change_reason': 'Attempt to erase basis'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invoices_split_shop_terms_and_print_only_manual_waiver_notes(self):
        from django.template.loader import render_to_string
        from estate_app.views import consolidated_invoice_context, invoice_context, selected_invoice_contexts
        first = self.bill(self.terms[0], full_month_rent=Decimal('3000'),
                          holiday_start_date=dt.date(2026, 6, 10), holiday_end_date=dt.date(2026, 6, 19))
        second = self.bill(self.terms[1], full_month_rent=Decimal('4000'))
        later = self.bill(self.terms[0], month=7)
        groups = selected_invoice_contexts([first, second, later])
        self.assertEqual(len(groups), 2)
        self.assertIsNone(consolidated_invoice_context([first, second]))
        context = consolidated_invoice_context([first, later])
        self.assertEqual(context['shop_code'], 'A-101')
        self.assertEqual(context['line_items'][0]['holiday_waiver'], '1,000.00')
        html = render_to_string('invoice_format2.html', invoice_context(first))
        self.assertIn('A-101', html)
        self.assertNotIn('Holiday closure', html)
        self.assertIn('2,000.00', html)
        first.notes = "Office reviewed closure.\nSee case file <42>."
        html = render_to_string('invoice_format2.html', invoice_context(first))
        self.assertIn('Office reviewed closure.<br>See case file &lt;42&gt;.', html)
        bulk = render_to_string('bulk_invoice.html', {'print_invoices': selected_invoice_contexts([first, second])})
        self.assertTrue('A-101' in bulk and 'N-401' in bulk)
        self.assertIn('Office reviewed closure.', bulk)
        self.assertNotIn('Holiday closure', bulk)


class EstateBillingMigrationTests(ActivityTransactionTestCase):
    def test_upgrade_preserves_legacy_financial_values_and_audit_guards(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes('estate_app')
        try:
            executor = MigrationExecutor(connection)
            target = [('estate_app', '0005_protected_submissions')]
            executor.migrate(target)
            old = executor.loader.project_state(target).apps
            tenant = old.get_model('estate_app', 'Tenant').objects.create(name='Historical bill test', type='Shop')
            bill = old.get_model('estate_app', 'Bill').objects.create(tenant_id=tenant.pk, month=6, year=2026,
                rent=Decimal('2000'), electric=Decimal('100'), water=Decimal('50'), gst_on_rent=Decimal('360'),
                cgst_on_rent=Decimal('180'), sgst_on_rent=Decimal('180'), due_date=dt.date(2026, 7, 5),
                issue_date=dt.date(2026, 6, 30), invoice_no='HISTORIC/001', status='Partial')
            old.get_model('estate_app', 'Payment').objects.create(bill_id=bill.pk, amount=Decimal('700'),
                payment_date=dt.date(2026, 7, 2), receipt_no='Historical receipt')
            MigrationExecutor(connection).migrate(latest)
            current = Bill.objects.get(pk=bill.pk)
            self.assertIsNone(current.allotment_id)
            self.assertEqual(current.billing_category, 'legacy')
            self.assertEqual(current.billing_policy, 'legacy_receipt')
            self.assertIsNone(current.raised_date)
            self.assertIsNone(current.email_dispatched_at)
            self.assertIsNone(current.rate_snapshot)
            self.assertIsNone(current.area_snapshot)
            self.assertIsNone(current.full_month_rent)
            self.assertEqual((current.rent, current.electric, current.water, current.gst_on_rent, current.amount_paid),
                             (Decimal('2000'), Decimal('100'), Decimal('50'), Decimal('360'), Decimal('700')))
            self.assertEqual(current.due_date, dt.date(2026, 7, 5))
            self.assertEqual(current.status, 'Partial')
            retained = current.payments.get()
            self.assertEqual((retained.source, retained.operation_id, retained.receipt_no, retained.payment_date),
                             ('receipt', None, 'Historical receipt', dt.date(2026, 7, 2)))
            from estate_app.data_transfer.serialization import export_bytes, validate_data
            import json
            restored, _ = validate_data(json.loads(export_bytes()))
            self.assertTrue(any(isinstance(item.object, Bill) and item.object.pk == bill.pk for item in restored))
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                triggers = {row[0] for row in cursor.fetchall()}
            self.assertIn('bt_activity_no_delete', triggers)
            self.assertIn('bt_audit_estate_app_bill_update', triggers)
            current.notes = 'Retained historical evidence'
            current.save(update_fields=['notes'])
            self.assertEqual(ActivityEntry.objects.filter(record_type='estate_app.bill', record_id=str(current.pk),
                                                         action='update').latest('id').after['billing_category'], 'legacy')
        finally:
            MigrationExecutor(connection).migrate(latest)
