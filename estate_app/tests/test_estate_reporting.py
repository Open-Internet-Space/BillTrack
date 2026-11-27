import datetime as dt
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from estate_app.email_drafts.service import generate
from estate_app.models import Allotment, Bill, EmailTemplate, Payment, RentRevision, SecurityMovement, Shop, SystemSettings
from estate_app.reminders.service import preview
from estate_app.tests.test_estate_charges import charge_term, assessed_charge


class EstateReportingTests(TestCase):
    def setUp(self):
        self.term = charge_term()
        self.user = User.objects.create_superuser('reports-supervisor')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        person = self.term.tenant
        person.email = 'shop@example.org'
        person.gst_applicable = False
        person.penalty_type = 'none'
        person.save()
        self.bill = Bill.objects.create(tenant=person, allotment=self.term, billing_category='allotment',
            billing_policy='notices_368_369', year=2026, month=6, full_month_rent=3000,
            holiday_start_date=dt.date(2026,6,10), holiday_end_date=dt.date(2026,6,19),
            rent_override_reason='Filed award basis', rate_exception_reference='FILE-9',
            raised_date=dt.date(2026,6,1))

    def test_confirmed_dispatch_drives_award_labelled_reminder_and_draft(self):
        today = dt.date(2026,6,12)
        self.assertEqual(preview(today)[0], [])
        self.bill.email_dispatched_at = dt.datetime(2026,6,10,9,tzinfo=dt.timezone.utc)
        self.bill.dispatch_sender = self.user
        self.bill.dispatch_recipient = 'shop@example.org'
        self.bill.dispatch_message_reference = 'Actual filed email'
        self.bill.save()
        groups, _ = preview(today)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['items'][0]['award'], self.term.award_reference)
        draft = generate(self.term.tenant_id, [self.bill.pk], EmailTemplate(name='Notice', subject='Payment', body='{bill_details}'))
        for evidence in (self.bill.invoice_no, '2026-06-08', 'Remaining principal: INR 2000.00'):
            self.assertIn(evidence, draft['body'])
        self.assertNotIn(self.term.award_reference, draft['body'])

    def test_estate_statement_isolates_legacy_and_security_from_shop_dues(self):
        Payment.objects.create(bill=self.bill, amount=200, payment_date=dt.date(2026,6,8))
        Bill.objects.create(tenant=self.term.tenant, year=2026, month=5, rent=70)
        assessed_charge(self.term)
        SecurityMovement.objects.create(original_award=self.term,kind='received',amount=500,
            effective_date=dt.date(2026,11,1),reference='Receipt',reason='Actual deposit',recorded_by=self.user)
        options = {'report':'estate','to':'2026-11-12'}
        data = self.api.get('/api/reports/', options)
        self.assertEqual(data.status_code, 200, data.content)
        self.assertEqual(data.json()['totals']['total_due'], '2870.00')
        scoped = self.api.get('/api/reports/', {**options,'allotment':self.term.pk}).json()
        for key,expected in {'total_due':'2800.00','holiday_waiver':'1000.00','security_held':'500.00',
                             'received':'200.00','charge_due':'1000.00'}.items():
            self.assertEqual(scoped['totals'][key], expected)
        historical = self.api.get('/api/reports/', {**options,'allotment':self.term.pk,'to':'2026-06-07'}).json()
        self.assertEqual(historical['totals']['total_due'],'2000.00')
        self.assertEqual(historical['totals']['received'],'0.00')
        term = self.api.get(f'/api/allotments/{self.term.pk}/').json()
        self.assertEqual(term['total_due'], '2800.00')
        for kind in ('legacy_review','bill_due'):
            attention = self.api.get('/api/estate/attention/', {'kind':kind}).json()['results']
            self.assertEqual(len(attention), 1)
            self.assertEqual(attention[0]['tenant'], self.term.tenant_id)
    def test_linking_legacy_invoice_keeps_reminder_history_for_that_bill_only(self):
        from estate_app.models import ReminderSubmission

        today = dt.date(2026, 6, 25)
        bill = Bill.objects.create(tenant=self.term.tenant, year=2026, month=5, rent=100,
                                   issue_date=dt.date(2026, 6, 5))
        groups, _ = preview(today)
        reminder = groups[0]['items'][0]
        self.assertEqual(reminder['bill_id'], bill.pk)
        ReminderSubmission.objects.create(allottee_uuid=bill.tenant.uuid, send_date=today,
            recipient=bill.tenant.email, status='accepted', items=[reminder])
        bill.allotment = self.term
        bill.billing_category = 'allotment'
        bill.save()
        other = Bill.objects.create(tenant=bill.tenant, year=bill.year, month=bill.month, rent=100,
                                    issue_date=bill.issue_date)
        groups, _ = preview(today + dt.timedelta(days=1))
        self.assertEqual([item['bill_id'] for group in groups for item in group['items']], [other.pk])

    def test_consolidated_print_keeps_monthly_notes_and_omits_internal_award_references(self):
        profile = SystemSettings.get_settings()
        profile.letterhead_name = 'Synthetic test organisation'
        profile.save()
        RentRevision.objects.create(original_award=self.term, effective_date=dt.date(2026, 4, 1),
            rate=20, approval_reference='Filed rate 42', reason='Reviewed accepted bid')
        bills = [Bill.objects.create(tenant=self.term.tenant, allotment=self.term,
            billing_category='allotment', billing_policy='notices_368_369', month=month,
            year=2026, full_month_rent=3000, raised_date=dt.date(2026, month, 1))
            for month in (7, 8)]
        bills[0].notes = 'Reviewed July adjustment'
        bills[0].save()
        other_term = Allotment.objects.create(tenant=self.term.tenant,
            shop=Shop.objects.create(code='SECOND-101', name='Second shop', category='utility'),
            source_notice=self.term.source_notice, award_reference='Second award',
            letter_issued_on=self.term.letter_issued_on, start_date=self.term.start_date,
            end_date=self.term.end_date, actual_area=150, measurement_reference='Second measurement')
        bills.append(Bill.objects.create(tenant=self.term.tenant, allotment=other_term,
            billing_category='allotment', year=2026, month=7, full_month_rent=500))
        bills.append(Bill.objects.create(tenant=self.term.tenant, year=2026, month=7, rent=250))
        self.client.force_login(self.user)
        response = self.client.get('/api/invoice/bulk/', {'ids': ','.join(str(b.pk) for b in bills)})
        self.assertContains(response, 'Consolidated Month-wise Charges', count=1)
        self.assertNotContains(response, 'Current Month Charges')
        self.assertNotContains(response, self.term.award_reference)
        self.assertNotContains(response, other_term.award_reference)
        pending = self.api.get('/api/reports/', {'report': 'pending', 'to': '2026-11-12'}).json()
        self.assertNotIn('shop', [column['key'] for column in pending['columns']])
        self.assertEqual({row['award'] for row in pending['rows']},
                         {self.term.award_reference, other_term.award_reference, 'Unassigned'})
        self.assertNotContains(response, 'Filed rate 42')
        self.assertNotContains(response, 'rent basis')
        self.assertContains(response, 'Jul 2026 note: Reviewed July adjustment', count=1)
        single = self.client.get(f'/api/invoice/{bills[0].pk}/')
        self.assertNotContains(single, 'Rent basis')
        self.assertContains(single, 'Reviewed July adjustment', count=1)
