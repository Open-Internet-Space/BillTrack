import datetime as dt

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from estate_app.models import ActivityEntry, Bill, Payment
from estate_app.tests.test_estate_charges import charge_term


class LegacyReviewTests(TestCase):
    def setUp(self):
        self.term = charge_term()
        self.boss = User.objects.create_superuser('reviewer', password='test-only')
        self.api = APIClient()
        self.api.force_authenticate(self.boss)
        self.bill = Bill.objects.create(tenant=self.term.tenant, month=6, year=2026, rent=1000,
                                        issue_date=dt.date(2026, 6, 5))
        Payment.objects.create(bill=self.bill, amount=100, receipt_no='R-101',
                               payment_date=dt.date(2026, 6, 15))
        self.url = f'/api/bills/{self.bill.pk}/legacy-'
        self.link = dict(action='link', allotment=self.term.pk, reason='Verified original shop award')

    def review(self, data):
        response = self.api.post(self.url + 'preview/', data, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def confirm(self, preview):
        return self.api.post(self.url + 'confirm/', {'confirmation': preview['confirmation']}, format='json')

    def test_link_changes_only_assignment_and_retries_once(self):
        before = Bill.objects.values().get(pk=self.bill.pk)
        receipts = list(Payment.objects.values())
        preview = self.review(self.link)
        self.assertEqual(Bill.objects.values().get(pk=self.bill.pk), before)
        self.assertEqual(self.confirm(preview).status_code, 200)
        after = Bill.objects.values().get(pk=self.bill.pk)
        self.assertEqual({k for k in before if before[k] != after[k]}, {'allotment_id', 'billing_category'})
        self.assertEqual(list(Payment.objects.values()), receipts)
        self.assertTrue(self.confirm(preview).json()['already_applied'])
        self.assertEqual(ActivityEntry.objects.filter(reason=self.link['reason']).count(), 1)

    def test_conversion_preserves_receipts_and_previews_new_deadline(self):
        self.assertEqual(self.confirm(self.review(self.link)).status_code, 200)
        receipts = list(Payment.objects.values())
        preview = self.review(dict(action='convert', raised_date='2026-06-01',
            email_dispatched_at='2026-06-09T10:30:00+05:30', dispatch_recipient='shop@example.org',
            dispatch_message_reference='Sent item 103', dispatch_sender=self.boss.pk,
            rent_override_reason='Historical billed rent verified', rate_exception_reference='Office file 14',
            reason='Checked filed invoice and dispatch evidence'))
        self.assertEqual(preview['before']['due_date'], '2026-06-10')
        self.assertEqual(preview['after']['due_date'], '2026-06-08')
        self.assertEqual(preview['after']['interest_start'], '2026-06-09')
        self.assertEqual(self.confirm(preview).status_code, 200)
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.billing_policy, 'notices_368_369')
        self.assertEqual(self.bill.total_amount, self.bill.rent + self.bill.gst_on_rent)
        self.assertEqual(list(Payment.objects.values()), receipts)
        self.assertTrue(self.confirm(preview).json()['already_applied'])

    def test_staff_denied_and_changed_receipt_invalidates_review(self):
        preview = self.review(self.link)
        user = User.objects.create_user('other', is_staff=True)
        self.api.force_authenticate(user)
        self.assertEqual(self.api.post(self.url+'preview/', self.link, format='json').status_code, 403)
        self.assertEqual(self.confirm(preview).status_code, 403)
        self.api.force_authenticate(self.boss)
        Payment.objects.create(bill=self.bill, amount=10, payment_date=dt.date(2026, 6, 16))
        self.assertEqual(self.confirm(preview).status_code, 400)
        self.bill.refresh_from_db()
        self.assertIsNone(self.bill.allotment_id)

    def test_admin_review_confirms_only_displayed_change(self):
        self.client.force_login(self.boss)
        path = f'/admin/estate_app/bill/{self.bill.pk}/legacy-review/'
        self.assertContains(self.client.get(path), 'Assign this bill')
        page = self.client.post(path, self.link)
        self.assertContains(page, 'R-101')
        self.bill.refresh_from_db()
        self.assertIsNone(self.bill.allotment_id)
        response = self.client.post(path, {'confirmation': page.context['review']['confirmation']})
        self.assertEqual(response.status_code, 302)
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.allotment_id, self.term.pk)

    def test_duplicate_period_and_inconsistent_historical_evidence_rejected(self):
        bill = Bill.objects.create(tenant=self.term.tenant, allotment=self.term, billing_category='allotment',
                                   month=6, year=2026, rent=1)
        self.assertEqual(self.api.post(self.url+'preview/', self.link, format='json').status_code, 400)
        bill.delete()
        self.assertEqual(self.confirm(self.review(self.link)).status_code, 200)
        for data in ({'raised_date': '2026-07-01'}, {'raised_date': '2026-06-01','dispatch_recipient':'shop@example.org'}):
            response = self.api.post(self.url+'preview/', {'action':'convert','reason':'Check evidence',**data}, format='json')
            self.assertEqual(response.status_code, 400)
