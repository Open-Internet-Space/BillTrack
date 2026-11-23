import datetime as dt
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch
from rest_framework.test import APIClient

from estate_app.models import Allotment, Bill, Payment, Shop, Tenant


class NoticeArithmeticTests(SimpleTestCase):
    def test_annual_revision_rounds_rate_and_never_repeats_as_of_increases(self):
        from estate_app.estate.billing import annual_revisions
        self.assertEqual(annual_revisions(Decimal('12'), dt.date(2025, 7, 1), dt.date(2026, 4, 1)),
                         [{'effective_date': dt.date(2026, 4, 1), 'rate': Decimal('12.6000')}])
        self.assertEqual(annual_revisions(Decimal('12.6'), dt.date(2026, 4, 1), dt.date(2026, 12, 31)), [])
        self.assertEqual(annual_revisions(Decimal('12.6'), dt.date(2026, 8, 1), dt.date(2027, 4, 1)),
                         [{'effective_date': dt.date(2027, 4, 1), 'rate': Decimal('13.2300')}])
        self.assertEqual(annual_revisions(Decimal('10.0001'), dt.date(2024, 1, 1), dt.date(2027, 4, 1))[-1]['rate'], Decimal('11.0251'))

    def test_simple_interest_rounds_only_the_final_payment_segment_total(self):
        from estate_app.estate.billing import notice_interest
        start = dt.date(2026, 11, 8)
        self.assertEqual(notice_interest(Decimal('1000'), start, start + dt.timedelta(days=10), []), Decimal('3.29'))
        self.assertEqual(notice_interest(Decimal('1000'), start, start + dt.timedelta(days=10),
            [(start + dt.timedelta(days=5), Decimal('400'))]), Decimal('2.63'))
        self.assertEqual(notice_interest(Decimal('1000'), start, start + dt.timedelta(days=10),
            [(start, Decimal('1000'))]), Decimal('0.00'))
        self.assertEqual(notice_interest(Decimal('1000'), start, start + dt.timedelta(days=10),
            [(start + dt.timedelta(days=20), Decimal('1000'))]), Decimal('3.29'))
        self.assertEqual(notice_interest(Decimal('1000'), dt.date(2028, 2, 28), dt.date(2028, 3, 1), []), Decimal('0.66'))
        self.assertEqual(notice_interest(Decimal('1000'), None, start, []), Decimal('0.00'))


class RentRevisionTests(TestCase):
    def setUp(self):
        self.assertIn('rentrevision', apps.all_models['estate_app'], 'Reviewed rent schedule is not implemented yet')
        self.Rate = apps.get_model('estate_app', 'RentRevision')
        self.tenant = Tenant.objects.create(name='Rate schedule example', type='Shop')
        shop = Shop.objects.create(code='RATE-101', name='Synthetic rate shop', category='utility')
        self.term = Allotment.objects.create(shop=shop, tenant=self.tenant, source_notice='368/2025',
            award_reference='Rate schedule award', letter_issued_on=dt.date(2025, 7, 1),
            start_date=dt.date(2025, 7, 1), end_date=dt.date(2026, 6, 30), actual_area=Decimal('150'),
            measurement_reference='Synthetic actual measurement')

    def base(self, **changes):
        return self.Rate.objects.create(**{**dict(original_award=self.term, effective_date=dt.date(2025, 7, 1),
            rate=Decimal('12'), approval_reference='Accepted bid 12 per sq ft', reason='Reviewed original accepted rate'), **changes})

    def test_reviewed_base_and_annual_schedule_use_actual_area(self):
        from estate_app.estate.billing import rent_schedule
        base = self.base()
        before = rent_schedule(self.term, 2026, 3)
        self.assertEqual(before['full_month_rent'], Decimal('1800.00'))
        self.assertEqual(before['revision_id'], base.pk)
        due = rent_schedule(self.term, 2026, 4)
        self.assertEqual(due['missing_revision_dates'], [dt.date(2026, 4, 1)])
        self.assertEqual(due['proposed_rate'], Decimal('12.6000'))
        revised = self.base(effective_date=dt.date(2026, 4, 1), rate=Decimal('12.6000'), approval_reference='April approval')
        after = rent_schedule(self.term, 2026, 4)
        self.assertEqual(after['full_month_rent'], Decimal('1890.00'))
        self.assertEqual(after['missing_revision_dates'], [])
        self.assertEqual(after['revision_id'], revised.pk)
        with self.assertRaises(ValidationError):
            self.base(effective_date=dt.date(2026, 4, 1), rate=Decimal('13.2300'))

    def test_missing_rates_and_unreviewed_or_invalid_revisions_are_rejected(self):
        from estate_app.estate.billing import rent_schedule
        with self.assertRaises(ValidationError):
            rent_schedule(self.term, 2026, 1)
        for changes in [dict(rate=0), dict(rate=-1), dict(approval_reference=''), dict(reason='')]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.base(**changes)
        self.base()
        for changes in [dict(effective_date=dt.date(2025, 8, 1)),
                        dict(effective_date=dt.date(2026, 4, 1), rate=Decimal('13')),
                        dict(effective_date=dt.date(2027, 4, 1), rate=Decimal('13.2300'))]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.base(**changes)

    def test_renewals_share_the_original_schedule_and_late_as_of_does_not_back_apply(self):
        from estate_app.estate.billing import rent_schedule
        from .test_estate_charges import settle_extension_fee
        settle_extension_fee(self.term)
        renewal = Allotment.objects.create(shop=self.term.shop, tenant=self.tenant, source_notice='368/2025',
            award_reference='Rate schedule extension', letter_issued_on=dt.date(2026, 7, 1),
            start_date=dt.date(2026, 7, 1), end_date=dt.date(2027, 6, 30), actual_area=Decimal('150'),
            measurement_reference='Retained actual measurement', renewal_of=self.term,
            performance_reference='Satisfactory performance', approval_reference='Extension approval')
        with self.assertRaises(ValidationError):
            self.base(original_award=renewal)
        self.base(effective_date=dt.date(2026, 4, 1), rate=Decimal('12.6000'))
        result = rent_schedule(renewal, 2026, 7)
        self.assertEqual(result['full_month_rent'], Decimal('1890.00'))
        self.assertFalse(result['missing_revision_dates'])

    def test_rate_api_previews_without_approving_and_rejects_duplicate_increase(self):
        api = APIClient()
        self.assertEqual(api.get('/api/rent-revisions/').status_code, 401)
        api.force_authenticate(User.objects.create_user('rate-review-staff'))
        response = api.post('/api/rent-revisions/', {'original_award': self.term.pk,
            'effective_date': '2025-07-01', 'rate': '12.0000', 'approval_reference': 'Accepted bid',
            'reason': 'Reviewed original rate as of letter'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        preview = api.get(f"/api/rent-revisions/{response.data['id']}/annual-preview/?through=2026-04-01")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['revisions'][0], {'effective_date': '2026-04-01', 'rate': '12.6000'})
        self.assertEqual(self.Rate.objects.count(), 1)
        data = {'original_award': self.term.pk, 'effective_date': '2026-04-01', 'rate': '12.6000',
                'approval_reference': 'April approval', 'reason': 'Approved 5% revision'}
        self.assertEqual(api.post('/api/rent-revisions/', data, format='json').status_code, 201)
        self.assertEqual(api.post('/api/rent-revisions/', data, format='json').status_code, 400)
        self.assertEqual(self.Rate.objects.count(), 2)
        self.assertEqual(api.get(f"/api/rent-revisions/{response.data['id']}/annual-preview/?through=9999-12-31").status_code,400)


class NoticeBillTests(TestCase):
    def setUp(self):
        self.assertTrue(hasattr(Bill, 'billing_policy'), 'Notice billing policy is not implemented yet')
        self.enterContext(patch('django.utils.timezone.localdate', return_value=dt.date(2026, 11, 30)))
        self.user = User.objects.create_user('notice-dispatch-staff')
        self.tenant = Tenant.objects.create(name='Notice arithmetic example', type='Shop',
                                            gst_applicable=False, penalty_type='none')
        self.term = Allotment.objects.create(shop=Shop.objects.create(code='NOTICE-101', name='Notice example', category='utility'),
            tenant=self.tenant, source_notice='368/2025', award_reference='Synthetic notice award',
            letter_issued_on=dt.date(2026, 1, 1), start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 12, 31),
            actual_area=100, measurement_reference='Synthetic measurement')
        self.rate = apps.get_model('estate_app', 'RentRevision').objects.create(original_award=self.term,
            effective_date=dt.date(2026, 11, 1), rate=Decimal('10'), approval_reference='Reviewed accepted rate',
            reason='Explicit rate as of November; previous increases included')

    def bill(self, **changes):
        values = dict(tenant=self.tenant, allotment=self.term, billing_category='allotment',
            billing_policy='notices_368_369', year=2026, month=11, full_month_rent=Decimal('1000'),
            raised_date=dt.date(2026, 11, 1), email_dispatched_at=dt.datetime(2026, 11, 1, 10, tzinfo=dt.timezone.utc),
            dispatch_recipient='synthetic@example.invalid', dispatch_message_reference='Synthetic confirmed message',
            dispatch_sender=self.user)
        values.update(changes)
        return Bill.objects.create(**values)

    def test_raised_deadline_is_independent_of_late_dispatch(self):
        bill = self.bill(email_dispatched_at=dt.datetime(2026, 11, 10, 10, tzinfo=dt.timezone.utc))
        self.assertEqual(bill.due_date, dt.date(2026, 11, 8))
        self.assertEqual(bill.penalty_start_date, dt.date(2026, 11, 10))
        self.assertEqual(bill.accrued_penalty(dt.date(2026, 11, 10)), Decimal('0'))
        self.assertEqual(bill.accrued_penalty(dt.date(2026, 11, 20)), Decimal('3.29'))
        self.assertIsNone(bill.issue_date)
        self.assertEqual(bill.receipt_status, 'Email Dispatch Confirmed')

    def test_interest_uses_fixed_policy_and_dated_principal_receipts(self):
        bill = self.bill()
        Payment.objects.create(bill=bill, amount=Decimal('400'), payment_date=dt.date(2026, 11, 13))
        bill.refresh_from_db()
        self.assertEqual(bill.accrued_penalty(dt.date(2026, 11, 18)), Decimal('2.63'))
        Payment.objects.create(bill=bill, amount=Decimal('600'), payment_date=dt.date(2026, 11, 18))
        bill.refresh_from_db()
        self.assertEqual(bill.penalty_accrued, Decimal('2.63'))
        self.assertEqual(bill.penalty, Decimal('2.63'))
        self.assertEqual(bill.status, 'Partial')
        Payment.objects.create(bill=bill, amount=0, penalty_paid=Decimal('2.63'), payment_date=dt.date(2026, 11, 19))
        bill.refresh_from_db()
        self.assertEqual(bill.status, 'Paid')
        self.assertEqual(bill.penalty, Decimal('0'))

    def test_draft_and_undispatched_final_invoice_have_no_interest(self):
        bill = self.bill(raised_date=None, email_dispatched_at=None, dispatch_recipient='',
                         dispatch_message_reference='', dispatch_sender=None)
        self.assertIsNone(bill.due_date)
        self.assertEqual(bill.receipt_status, 'Draft')
        self.assertEqual(bill.penalty, Decimal('0'))
        bill.raised_date = dt.date(2026, 11, 1)
        bill.save()
        self.assertEqual(bill.due_date, dt.date(2026, 11, 8))
        self.assertEqual(bill.receipt_status, 'Pending Email Dispatch')
        self.assertEqual(bill.penalty, Decimal('0'))

    def test_dispatch_needs_confirmed_evidence_and_india_local_day(self):
        for changes in [dict(dispatch_recipient=''), dict(dispatch_message_reference=''),
                        dict(dispatch_sender=None), dict(raised_date=None),
                        dict(email_dispatched_at=timezone.now() + dt.timedelta(days=1)),
                        dict(email_dispatched_at=dt.datetime(2026, 10, 31, 10, tzinfo=dt.timezone.utc))]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.bill(**changes)
        bill = self.bill(email_dispatched_at=dt.datetime(2026, 11, 10, 20, tzinfo=dt.timezone.utc))
        self.assertEqual(bill.penalty_start_date, dt.date(2026, 11, 11))

    def test_partial_unrelated_save_preserves_dispatch_and_due_date(self):
        bill = self.bill()
        bill.raised_date = dt.date(2026, 11, 2)
        bill.email_dispatched_at = None
        bill.notes = 'Only update this note'
        bill.save(update_fields=['notes'])
        bill.refresh_from_db()
        self.assertEqual(bill.raised_date, dt.date(2026, 11, 1))
        self.assertIsNotNone(bill.email_dispatched_at)
        self.assertEqual(bill.due_date, dt.date(2026, 11, 8))

    def test_bill_retains_reviewed_area_rate_and_reference_snapshots(self):
        bill = self.bill()
        self.assertEqual(bill.rent_revision_id, self.rate.pk)
        self.assertEqual(bill.rate_snapshot, Decimal('10.0000'))
        self.assertEqual(bill.area_snapshot, Decimal('100.0000'))
        self.assertEqual(bill.rent_revision_reference, 'Reviewed accepted rate')
        self.term.actual_area = Decimal('110')
        self.term.save()
        bill.notes = 'Only correct a note after remeasurement'
        bill.save()
        bill.refresh_from_db()
        self.assertEqual((bill.full_month_rent, bill.area_snapshot), (Decimal('1000'), Decimal('100')))
        self.rate.rate = Decimal('11')
        with self.assertRaises(ValidationError):
            self.rate.save()

    def test_missing_april_approval_blocks_final_issue_but_allows_a_draft(self):
        self.rate.effective_date = dt.date(2026, 3, 1)
        self.rate.save()
        with self.assertRaises(ValidationError):
            self.bill()
        draft = self.bill(raised_date=None, email_dispatched_at=None, dispatch_recipient='',
                          dispatch_message_reference='', dispatch_sender=None)
        self.assertEqual(draft.receipt_status, 'Draft')
        self.rate.__class__.objects.create(original_award=self.term, effective_date=dt.date(2026, 4, 1),
            rate=Decimal('10.5'), approval_reference='Approved April revision', reason='5% annual revision')
        draft.raised_date = dt.date(2026, 11, 1)
        draft.save()
        draft.refresh_from_db()
        self.assertEqual(draft.full_month_rent, Decimal('1050'))
        self.assertEqual(draft.rate_snapshot, Decimal('10.5000'))

    def test_manual_rent_difference_needs_review_reason_and_stays_authoritative(self):
        with self.assertRaises(ValidationError):
            self.bill(full_month_rent=Decimal('900'))
        bill = self.bill(full_month_rent=Decimal('900'), rent_override_reason='Approved original billing correction REF-1')
        self.assertEqual(bill.full_month_rent, Decimal('900'))
        self.assertEqual(bill.rent, Decimal('900'))

    def test_api_selects_notice_policy_and_owns_dispatch_actor(self):
        api = APIClient()
        api.force_authenticate(self.user)
        payload = {'tenant': self.tenant.pk, 'allotment': self.term.pk, 'month': 11, 'year': 2026,
                   'raised_date': '2026-11-01', 'email_dispatched_at': '2026-11-10T10:00:00Z',
                   'dispatch_recipient': 'synthetic@example.invalid', 'dispatch_message_reference': 'Confirmed message',
                   'dispatch_sender': 99999}
        response = api.post('/api/bills/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['billing_policy'], 'notices_368_369')
        self.assertEqual(response.data['full_month_rent'], '1000.00')
        self.assertEqual(response.data['due_date'], '2026-11-08')
        self.assertEqual(response.data['dispatch_sender'], self.user.pk)
        self.assertEqual(response.data['rate_snapshot'], '10.0000')
        self.assertEqual(api.post('/api/bills/', {**payload, 'month': 12,
            'billing_policy': 'legacy_receipt'}, format='json').status_code, 400)
        self.assertEqual(api.patch(f"/api/bills/{response.data['id']}/", {'billing_policy': 'legacy_receipt',
            'change_reason': 'Attempt ordinary policy conversion'}, format='json').status_code, 400)

    def test_preview_selects_each_month_rate_before_the_holiday_waiver(self):
        self.rate.effective_date = dt.date(2026, 3, 1)
        self.rate.save()
        self.rate.__class__.objects.create(original_award=self.term, effective_date=dt.date(2026, 4, 1),
            rate=Decimal('10.5'), approval_reference='Approved April revision', reason='5% annual revision')
        api = APIClient()
        api.force_authenticate(self.user)
        response = api.post('/api/bills/preview/', {'tenant': self.tenant.pk, 'allotment': self.term.pk,
            'from_month': 3, 'from_year': 2026, 'to_month': 4, 'to_year': 2026,
            'holiday_start_date': '2026-03-31', 'holiday_end_date': '2026-04-01'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item['full_month_rent'] for item in response.data['months']], ['1000.00', '1050.00'])
        self.assertEqual([item['rent'] for item in response.data['months']], ['967.74', '1015.00'])
        self.assertEqual([item['rate_snapshot'] for item in response.data['months']], ['10.0000', '10.5000'])

    def test_reports_and_dashboard_use_notice_dates_and_exclude_draft_debt(self):
        from estate_app.views.reports import bill_position
        bill = self.bill(email_dispatched_at=dt.datetime(2026, 11, 10, 10, tzinfo=dt.timezone.utc))
        position = bill_position(bill, dt.date(2026, 11, 20))
        self.assertEqual(position['penalty_accrued'], Decimal('3.29'))
        self.assertEqual(position['days_overdue'], 10)
        draft = self.bill(month=12, raised_date=None, email_dispatched_at=None, dispatch_recipient='',
                          dispatch_message_reference='', dispatch_sender=None)
        self.assertEqual(bill_position(draft, dt.date(2026, 12, 31))['billed'], 0)
        api = APIClient()
        api.force_authenticate(self.user)
        dashboard = api.get('/api/dashboard/').data
        self.assertEqual(dashboard['total_billed'], 1000)
        self.assertEqual(dashboard['total_outstanding'], 1000)

    def test_invoice_policy_wording_and_draft_deadline(self):
        from django.template.loader import render_to_string
        from estate_app.views import invoice_context, consolidated_invoice_context, selected_invoice_contexts
        bill = self.bill()
        html = render_to_string('invoice_format2.html', invoice_context(bill))
        self.assertIn('seven calendar days', html)
        self.assertIn('12%', html)
        self.assertNotIn('Due date is 5 day', html)
        draft = self.bill(month=12, raised_date=None, email_dispatched_at=None, dispatch_recipient='',
                          dispatch_message_reference='', dispatch_sender=None)
        self.assertEqual(invoice_context(draft)['due_date'], 'Draft — not raised')
        self.assertEqual(consolidated_invoice_context([draft])['due_date'], 'Draft — not raised')
        groups=selected_invoice_contexts([bill,draft])
        self.assertEqual(len(groups),2)
        self.assertIsNone(consolidated_invoice_context([bill,draft]))
        bulk = render_to_string('bulk_invoice.html', {'print_invoices': groups})
        self.assertTrue('seven calendar days' in bulk)
        self.assertTrue('DRAFT — NOT RAISED' in bulk)

    def test_admin_validates_notice_evidence_with_the_acting_user(self):
        from django.forms.models import model_to_dict
        from types import SimpleNamespace
        from estate_app.admin import BillAdminForm
        bill = self.bill()
        actor = User.objects.create_user('correcting-dispatch-staff')
        form = BillAdminForm(data={**model_to_dict(bill),
            'email_dispatched_at': '2026-11-10T15:30:00+05:30', 'dispatch_sender': self.user.pk},
            instance=bill, request=SimpleNamespace(user=actor))
        self.assertTrue(form.is_valid(), form.errors)
        bill = form.save()
        self.assertEqual(bill.dispatch_sender_id, actor.pk)
        self.assertEqual(bill.due_date, dt.date(2026, 11, 8))
        self.assertEqual(bill.penalty_start_date, dt.date(2026, 11, 10))

    def test_notice_raising_correction_cannot_invalidate_retained_payments(self):
        bill = self.bill(email_dispatched_at=None, dispatch_sender=None, dispatch_recipient='',
                         dispatch_message_reference='')
        payment = Payment.objects.create(bill=bill, amount=100, payment_date=dt.date(2026, 11, 3))
        api = APIClient()
        api.force_authenticate(self.user)
        for proposed in (None, '2026-11-04'):
            with self.subTest(proposed=proposed):
                data = {'raised_date': proposed, 'change_reason': 'Reviewed date correction'}
                response = api.patch(f'/api/bills/{bill.pk}/', data, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                bill.refresh_from_db()
                self.assertEqual(bill.raised_date, dt.date(2026, 11, 1))
        payment.refresh_from_db()
        self.assertEqual(payment.amount, 100)

    def test_notice_receipts_require_a_raised_invoice_and_actual_payment_date(self):
        draft = self.bill(raised_date=None, email_dispatched_at=None, dispatch_recipient='',
                          dispatch_message_reference='', dispatch_sender=None)
        with self.assertRaises(ValidationError):
            Payment.objects.create(bill=draft, amount=Decimal('100'), payment_date=dt.date(2026, 11, 2))
        draft.raised_date = dt.date(2026, 11, 1)
        draft.save()
        for day in (dt.date(2026, 10, 31), dt.date(2026, 12, 1)):
            with self.subTest(day=day), self.assertRaises(ValidationError):
                Payment.objects.create(bill=draft, amount=Decimal('100'), payment_date=day)
        Payment.objects.create(bill=draft, amount=Decimal('1000'), payment_date=dt.date(2026, 11, 2))
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'Paid')

    def test_holiday_correction_previews_policy_interest_and_preserves_all_receipts(self):
        bill = self.bill()
        Payment.objects.create(bill=bill, amount=Decimal('1000'), payment_date=dt.date(2026, 11, 18), receipt_no='Principal retained')
        Payment.objects.create(bill=bill, amount=0, penalty_paid=Decimal('3.29'), payment_date=dt.date(2026, 11, 19), receipt_no='Interest retained')
        api = APIClient()
        api.force_authenticate(self.user)
        changes = {'holiday_start_date':'2026-11-10','holiday_end_date':'2026-11-19'}
        response = api.post(f'/api/bills/{bill.pk}/preview/', changes, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        preview = response.data['months'][0]
        self.assertEqual(preview['previous_interest_accrued'], '3.29')
        self.assertEqual(preview['interest_accrued'], '2.19')
        self.assertEqual(preview['excess_principal_paid'], '333.33')
        self.assertEqual(preview['excess_interest_paid'], '1.10')
        response = api.patch(f'/api/bills/{bill.pk}/', {**changes,'change_reason':'Reviewed actual closure and policy interest correction'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        bill.refresh_from_db()
        self.assertEqual(bill.penalty_accrued, Decimal('2.19'))
        self.assertEqual(bill.payments.count(), 2)
        self.assertEqual(sum(bill.payments.values_list('penalty_paid',flat=True)), Decimal('3.29'))

    def test_deadline_overdue_is_visible_even_while_interest_waits_for_dispatch(self):
        bill = self.bill(email_dispatched_at=None, dispatch_recipient='',dispatch_message_reference='',dispatch_sender=None)
        self.assertEqual(bill.days_overdue, 0)
        self.assertEqual(bill.payment_days_overdue, 22)
        self.assertTrue(bill.deadline_established)

    def test_missing_revision_attention_clears_only_after_an_approved_rate(self):
        self.rate.effective_date=dt.date(2026,3,1)
        self.rate.save()
        api=APIClient()
        api.force_authenticate(self.user)
        response=api.get('/api/estate/attention/?kind=revision_due')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['results'][0]['allotment'],self.term.pk)
        self.assertEqual(response.data['results'][0]['due_date'],'2026-04-01')
        self.rate.__class__.objects.create(original_award=self.term,effective_date=dt.date(2026,4,1),
            rate=Decimal('10.5'),approval_reference='Approved April rate',reason='Reviewed annual increase')
        self.assertEqual(api.get('/api/estate/attention/?kind=revision_due').data['results'],[])

    def test_mixed_policy_print_labels_each_month_without_a_false_shared_rule(self):
        from estate_app.views import consolidated_invoice_context, selected_invoice_contexts
        from django.template.loader import render_to_string
        notice=self.bill()
        legacy=self.bill(month=12,billing_policy='legacy_receipt',raised_date=None,email_dispatched_at=None,
                         dispatch_recipient='',dispatch_message_reference='',dispatch_sender=None)
        context=consolidated_invoice_context([notice,legacy])
        self.assertTrue(context['mixed_policies'])
        html=render_to_string('bulk_invoice.html',{'print_invoices':selected_invoice_contexts([notice,legacy])})
        self.assertTrue('Mixed billing policies' in html)
        self.assertTrue('Notices 368' in html and 'Legacy confirmed receipt' in html)

    def test_batch_update_cannot_erase_confirmed_dispatch_evidence(self):
        bill=self.bill()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Bill.objects.filter(pk=bill.pk).update(dispatch_recipient='')
        bill.refresh_from_db()
        self.assertEqual(bill.dispatch_recipient,'synthetic@example.invalid')

    def test_reviewed_month_correction_selects_the_rate_for_the_corrected_month(self):
        self.rate.effective_date=dt.date(2026,3,1)
        self.rate.save()
        revised=self.rate.__class__.objects.create(original_award=self.term,effective_date=dt.date(2026,4,1),
            rate=Decimal('10.5'),approval_reference='April approval',reason='Approved annual increase')
        bill=self.bill(month=3)
        api=APIClient()
        api.force_authenticate(self.user)
        response=api.patch(f'/api/bills/{bill.pk}/',{'month':4,'change_reason':'Correct reviewed billing period'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['full_month_rent'],'1050.00')
        self.assertEqual(response.data['rent_revision'],revised.pk)
