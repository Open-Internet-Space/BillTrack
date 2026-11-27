import datetime as dt
from decimal import Decimal
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from estate_app.models import ActivityEntry, Tenant
from estate_app.tests.transaction_case import ActivityTransactionTestCase


class EstateRecordTests(TestCase):
    def setUp(self):
        self.enterContext(patch('django.utils.timezone.localdate', return_value=dt.date(2026, 11, 13)))
        self.assertIn('shop', apps.all_models['estate_app'], 'Estate shop records are not implemented')
        self.Shop = apps.get_model('estate_app', 'Shop')
        self.Allotment = apps.get_model('estate_app', 'Allotment')
        self.Requirement = apps.get_model('estate_app', 'AllotmentRequirement')
        self.tenant = Tenant.objects.create(name='Estate test allottee', type='Shop')
        self.shop = self.Shop.objects.create(code=' a-101 ', name='Snacks', category='day_food')

    def term(self, **changes):
        values = dict(shop=self.shop, tenant=self.tenant, source_notice='368/2025',
                      award_reference='Synthetic award 1', letter_issued_on=dt.date(2025, 7, 1),
                      start_date=dt.date(2025, 7, 1), end_date=dt.date(2026, 6, 30),
                      actual_area=Decimal('150'), measurement_reference='Measurement 1')
        values.update(changes)
        return self.Allotment.objects.create(**values)

    def test_codes_are_canonical_and_unique_without_changing_legal_name(self):
        self.assertEqual(self.shop.code, 'A-101')
        with self.assertRaises(ValidationError):
            self.Shop.objects.create(code='a-101', name='Duplicate', category='utility')
        with self.assertRaises(ValidationError):
            self.Shop.objects.create(code='A\n102', name='Invalid', category='utility')
        self.assertEqual(self.tenant.name, 'Estate test allottee')

    def test_one_allottee_can_have_two_independent_shops(self):
        first = self.term()
        second_shop = self.Shop.objects.create(code='N-401', name='Night shop', category='night_utility')
        second = self.term(shop=second_shop, award_reference='Synthetic award 2')
        self.assertEqual(self.tenant.allotments.count(), 2)
        self.assertNotEqual(first.uuid, second.uuid)
        self.assertEqual(self.shop.occupancy_status, 'unknown')

    def test_inclusive_overlap_and_invalid_dates_or_area_are_rejected(self):
        self.term()
        for changes in [dict(start_date=dt.date(2026, 6, 30), end_date=dt.date(2027, 6, 29)),
                        dict(end_date=dt.date(2025, 6, 30)), dict(actual_area=0),
                        dict(termination_date=dt.date(2027, 1, 1), termination_reference='Order')]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.term(**changes)
        following = self.term(award_reference='Fresh award reference', letter_issued_on=dt.date(2026, 7, 1), start_date=dt.date(2026, 7, 1),
                              end_date=dt.date(2027, 6, 30))
        self.assertEqual(following.effective_end, dt.date(2027, 6, 30))

    def test_renewal_requires_approval_and_cannot_reset_extension_limit(self):
        from .test_estate_charges import settle_extension_fee
        original = self.term()
        previous = original
        for extension in (1, 2):
            values = dict(renewal_of=previous, start_date=dt.date(2025 + extension, 7, 1),
                          end_date=dt.date(2026 + extension, 6, 30))
            with self.assertRaises(ValidationError):
                self.term(**values)
            settle_extension_fee(previous)
            previous = self.term(**values, performance_reference='Satisfactory review',
                                 approval_reference=f'Extension order {extension}')
            self.assertEqual(previous.extension_number, extension)
            self.assertEqual(previous.original_award.pk, original.pk)
        with self.assertRaises(ValidationError):
            self.term(renewal_of=previous, start_date=dt.date(2028, 7, 1), end_date=dt.date(2029, 6, 30),
                      performance_reference='Satisfactory', approval_reference='Third extension')

    def test_original_award_identity_is_protected_after_notice_billing_or_extension(self):
        from estate_app.models import Bill, RentRevision
        original = self.term()
        RentRevision.objects.create(original_award=original, effective_date=dt.date(2025, 7, 1), rate=1,
                                    approval_reference='Rate approval', reason='Recorded rate')
        Bill.objects.create(tenant=self.tenant, allotment=original, billing_category='allotment',
                            billing_policy='notices_368_369', month=6, year=2026, rent=150,
                            full_month_rent=150, raised_date=dt.date(2026, 6, 1),
                            rate_exception_reference='Rate exception')
        original.source_notice = 'Other office file'
        with self.assertRaises(ValidationError):
            original.save()
        original.refresh_from_db()
        from .test_estate_charges import settle_extension_fee
        settle_extension_fee(original)
        renewal = self.term(renewal_of=original, start_date=dt.date(2026, 7, 1), end_date=dt.date(2027, 6, 30),
                            performance_reference='Satisfactory review', approval_reference='Approval file')
        other_shop = self.Shop.objects.create(code='B-202', name='Other shop', category='utility')
        original.shop = other_shop
        with self.assertRaises(ValidationError):
            original.save()
        self.assertEqual(renewal.shop_id, self.shop.pk)

    def test_contiguous_renewal_records_handover_without_inventing_new_possession(self):
        from estate_app.data_transfer.serialization import export_data, validate_data
        from estate_app.estate.security_api import refund_issues
        from .test_estate_charges import settle_extension_fee

        self.shop.availability_confirmed_on = dt.date(2025, 7, 1)
        self.shop.availability_reference = 'Initial availability'
        self.shop.save()
        original = self.term(possession_date=dt.date(2025, 7, 1), possession_reference='Actual possession')
        settle_extension_fee(original)
        renewal = self.term(renewal_of=original, start_date=dt.date(2026, 7, 1), end_date=dt.date(2027, 6, 30),
                            performance_reference='Satisfactory', approval_reference='Renewal order',
                            termination_date=dt.date(2026, 10, 31), termination_reference='Termination order')
        self.assertEqual(self.shop.occupancy_status, 'occupied')
        renewal.handover_date = dt.date(2026, 11, 1)
        renewal.handover_reference = 'Actual final handover'
        renewal.save()
        self.assertIsNone(renewal.possession_date)
        self.assertEqual(self.shop.occupancy_status, 'vacant')
        self.assertNotIn('Physical handover of the final term is not confirmed.', refund_issues(original))
        self.term(award_reference='Subsequent award', letter_issued_on=dt.date(2026, 11, 2),
                  start_date=dt.date(2026, 11, 2), end_date=dt.date(2027, 11, 1),
                  possession_date=dt.date(2026, 11, 2), possession_reference='New entry')
        validate_data(export_data())

    def test_expired_does_not_mean_vacant_and_handover_is_evidence_based(self):
        self.shop.availability_confirmed_on = dt.date(2025, 7, 1)
        self.shop.availability_reference = 'Initial available space'
        self.shop.save()
        term = self.term(possession_date=dt.date(2025, 7, 1), possession_reference='Possession memo')
        self.assertEqual(term.status, 'expired')
        self.assertEqual(self.shop.occupancy_status, 'occupied')
        self.assertEqual(term.vacation_due_date, dt.date(2026, 7, 30))
        term.handover_date = dt.date(2026, 8, 1)
        with self.assertRaises(ValidationError):
            term.save()
        term.handover_reference = 'Handover memo'
        term.save()
        self.assertEqual(self.shop.occupancy_status, 'vacant')

    def test_unknown_or_occupied_shop_cannot_be_possessed_by_another_allottee(self):
        term = self.term()
        term.possession_date = dt.date(2025, 7, 1)
        term.possession_reference = 'Possession memo'
        with self.assertRaises(ValidationError):
            term.save()
        self.shop.availability_confirmed_on = dt.date(2025, 7, 1)
        self.shop.availability_reference = 'Initial available space'
        self.shop.save()
        term.save()
        other = Tenant.objects.create(name='New occupant', type='Shop')
        with self.assertRaises(ValidationError):
            self.term(tenant=other, start_date=dt.date(2026, 7, 1), end_date=dt.date(2027, 6, 30),
                      possession_date=dt.date(2026, 7, 1), possession_reference='New possession')

    def test_original_award_requires_a_yearly_term_or_exception(self):
        with self.assertRaises(ValidationError):
            self.term(end_date=dt.date(2027, 6, 30))
        original = self.term(end_date=dt.date(2027, 6, 30), exception_reference='Approved duration exception')
        self.assertEqual(original.end_date, dt.date(2027, 6, 30))

    def test_first_possession_after_effective_expiry_is_rejected(self):
        self.shop.availability_confirmed_on = dt.date(2025, 7, 1)
        self.shop.availability_reference = 'Available space'
        self.shop.save()
        with self.assertRaises(ValidationError):
            self.term(possession_date=dt.date(2026, 7, 1), possession_reference='Late initial entry')

    def test_leap_year_annual_term_and_calendar_month_deadline(self):
        leap = self.term(letter_issued_on=dt.date(2024, 2, 29), start_date=dt.date(2024, 2, 29),
                         end_date=dt.date(2025, 2, 28))
        self.assertEqual(leap.status_on(dt.date(2025, 2, 28)), 'current')
        self.assertEqual(leap.status_on(dt.date(2025, 3, 1)), 'expired')
        self.assertEqual(leap.vacation_due_date, dt.date(2025, 3, 28))

    def test_references_protect_history_and_new_records_are_audited(self):
        term = self.term()
        for obj in (self.shop, self.tenant):
            with self.assertRaises(ProtectedError):
                obj.delete()
        entry = ActivityEntry.objects.filter(record_type='estate_app.allotment', record_id=str(term.pk)).get()
        self.assertEqual(entry.after['award_reference'], 'Synthetic award 1')
        self.assertEqual(entry.after['shop_id'], self.shop.pk)

    def test_requirement_verification_requires_submission_and_actor(self):
        term = self.term()
        requirement = self.Requirement.objects.create(allotment=term, kind='police',
                                                       due_date=dt.date(2025, 7, 31))
        self.assertEqual(requirement.status, 'overdue')
        requirement.verified_on = timezone.localdate()
        with self.assertRaises(ValidationError):
            requirement.save()

    def test_future_possession_dates_and_retired_shop_awards_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.term(possession_date=timezone.localdate() + dt.timedelta(days=1), possession_reference='Future')
        self.shop.active = False
        self.shop.save()
        today = timezone.localdate()
        with self.assertRaises(ValidationError):
            self.term(letter_issued_on=today, start_date=today,
                      end_date=today + dt.timedelta(days=100))


class EstateConcurrencyTests(ActivityTransactionTestCase):
    def test_two_concurrent_overlapping_awards_cannot_both_commit(self):
        import threading
        from django.db import OperationalError, close_old_connections

        Shop = apps.get_model('estate_app', 'Shop')
        Allotment = apps.get_model('estate_app', 'Allotment')
        tenant = Tenant.objects.create(name='Concurrent allottee', type='Shop')
        shop = Shop.objects.create(code='C-101', name='Concurrency test', category='utility')
        ready = threading.Barrier(2)
        outcomes = []

        def create_term():
            close_old_connections()
            try:
                ready.wait(timeout=5)
                Allotment.objects.create(shop_id=shop.pk, tenant_id=tenant.pk, source_notice='368/2025',
                    award_reference='Concurrent award', letter_issued_on=dt.date(2025, 7, 1),
                    start_date=dt.date(2025, 7, 1), end_date=dt.date(2026, 6, 30),
                    actual_area=150, measurement_reference='Measurement')
                outcomes.append('created')
            except (ValidationError, OperationalError):
                outcomes.append('conflict')
            finally:
                close_old_connections()

        threads = [threading.Thread(target=create_term) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ['created', 'conflict'])
        self.assertEqual(Allotment.objects.count(), 1)


class EstateMigrationTests(ActivityTransactionTestCase):
    def test_reverse_and_reapply_preserves_existing_audit_guards(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        tenant = Tenant.objects.create(name='Retained migration record', type='Shop')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes('estate_app')
        target = [('estate_app', '0005_protected_submissions')]
        try:
            executor.migrate(target)
            historical = executor.loader.project_state(target).apps
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                triggers = {row[0] for row in cursor.fetchall()}
            self.assertIn('bt_activity_no_delete', triggers)
            self.assertIn('bt_audit_estate_app_tenant_update', triggers)
            historical.get_model('estate_app', 'Tenant').objects.filter(pk=tenant.pk).update(contact='Synthetic contact')
            self.assertTrue(ActivityEntry.objects.filter(record_type='estate_app.tenant',
                record_id=str(tenant.pk), action='update').exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
