import datetime as dt
import importlib
import importlib.util
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from estate_app.models import Bill, Payment, Tenant


class HolidayCalculationTests(SimpleTestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('estate_app.estate.billing'), 'Holiday rent calculation is not implemented')
        self.calculate = importlib.import_module('estate_app.estate.billing').holiday_rent

    def test_inclusive_closure_and_actual_month_days(self):
        result = self.calculate(Decimal('3000'), 2026, 6, dt.date(2026, 6, 10), dt.date(2026, 6, 19))
        self.assertEqual(result, {'days_in_month': 30, 'closed_days': 10,
            'waiver_amount': Decimal('1000.00'), 'applicable_rent': Decimal('2000.00')})
        self.assertEqual(self.calculate(Decimal('3100'), 2026, 1, dt.date(2026, 1, 5),
            dt.date(2026, 1, 5))['applicable_rent'], Decimal('3000.00'))

    def test_cross_month_year_and_leap_dates_are_clipped_independently(self):
        start, end = dt.date(2027, 1, 20), dt.date(2027, 2, 10)
        self.assertEqual(self.calculate(Decimal('3100'), 2027, 1, start, end)['applicable_rent'], Decimal('1900.00'))
        self.assertEqual(self.calculate(Decimal('3100'), 2027, 2, start, end)['applicable_rent'], Decimal('1992.86'))
        self.assertEqual(self.calculate(Decimal('2900'), 2028, 2, dt.date(2028, 1, 1),
            dt.date(2028, 3, 1))['applicable_rent'], Decimal('0.00'))
        self.assertEqual(self.calculate(Decimal('3100'), 2026, 12, dt.date(2026, 12, 31),
            dt.date(2027, 1, 1))['applicable_rent'], Decimal('3000.00'))

    def test_no_closure_no_overlap_and_invalid_inputs(self):
        self.assertEqual(self.calculate(Decimal('3100'), 2026, 1)['applicable_rent'], Decimal('3100.00'))
        self.assertEqual(self.calculate(Decimal('3100'), 2026, 1, dt.date(2026, 2, 1),
            dt.date(2026, 2, 2))['closed_days'], 0)
        for amount, year, month, start, end in [
            (Decimal('-1'), 2026, 1, None, None), (Decimal('NaN'), 2026, 1, None, None),
            (Decimal('100'), 2026, 13, None, None),
            (Decimal('100'), 2026, 1, dt.date(2026, 1, 1), None),
            (Decimal('100'), 2026, 1, dt.date(2026, 1, 3), dt.date(2026, 1, 1)),
        ]:
            with self.subTest(values=(amount, year, month, start, end)), self.assertRaises(ValidationError):
                self.calculate(amount, year, month, start, end)


class HolidayBillTests(TestCase):
    def setUp(self):
        self.assertTrue(hasattr(Bill, 'full_month_rent'), 'Bill holiday evidence fields are not implemented')
        self.tenant = Tenant.objects.create(name='Holiday test allottee', type='Shop', gst_applicable=False, penalty_type='none')

    def bill(self, **changes):
        values = dict(tenant=self.tenant, year=2026, month=6, full_month_rent=Decimal('3000'),
            holiday_start_date=dt.date(2026, 6, 10), holiday_end_date=dt.date(2026, 6, 19))
        values.update(changes)
        return Bill.objects.create(**values)

    def test_net_rent_is_saved_with_evidence_and_utilities_are_unchanged(self):
        bill = self.bill(rent=Decimal('9999'), electric=Decimal('100'), water=Decimal('50'))
        self.assertEqual(bill.rent, Decimal('2000.00'))
        self.assertEqual(bill.full_month_rent, Decimal('3000.00'))
        self.assertEqual(bill.holiday_closed_days, 10)
        self.assertEqual(bill.holiday_waiver, Decimal('1000.00'))
        self.assertEqual(bill.total_amount, Decimal('2150.00'))
        bill.save()
        bill.refresh_from_db()
        self.assertEqual(bill.rent, Decimal('2000.00'))

    def test_gst_uses_reduced_rent(self):
        self.tenant.gst_applicable = True
        self.tenant.custom_gst_rate = Decimal('18')
        self.tenant.save()
        bill = self.bill()
        self.assertEqual(bill.gst_on_rent, Decimal('360.00'))
        self.assertEqual(bill.total_amount, Decimal('2360.00'))

    def test_fresh_default_settings_return_decimal_tax_for_decimal_rent(self):
        from estate_app.models import SystemSettings
        self.tenant.gst_applicable=True
        rate=self.tenant.get_gst_rate(SystemSettings())
        self.assertIsInstance(rate,Decimal)
        self.assertEqual(Bill(tenant=self.tenant,rent=Decimal('100')).calculate_gst(SystemSettings())[0],Decimal('18'))

    def test_full_closure_is_settled_without_fake_payment_but_utilities_remain_due(self):
        bill = self.bill(holiday_start_date=dt.date(2026, 6, 1), holiday_end_date=dt.date(2026, 6, 30))
        self.assertEqual(bill.status, 'Paid')
        self.assertEqual(bill.payments.count(), 0)
        bill.water = Decimal('50')
        bill.save()
        bill.refresh_from_db()
        self.assertEqual(bill.status, 'Unpaid')
        self.assertEqual(bill.balance_due, Decimal('50.00'))

    def test_clearing_closure_restores_original_basis_and_preserves_receipts(self):
        bill = self.bill()
        Payment.objects.create(bill=bill, amount=Decimal('2200'), receipt_no='Synthetic receipt')
        bill.refresh_from_db()
        self.assertEqual(bill.rent, Decimal('2000.00'))
        self.assertEqual(bill.amount_paid, Decimal('2200.00'))
        bill.holiday_start_date = bill.holiday_end_date = None
        bill.save()
        bill.refresh_from_db()
        self.assertEqual(bill.rent, Decimal('3000.00'))
        self.assertEqual(bill.balance_due, Decimal('800.00'))
        self.assertEqual(bill.status, 'Partial')
        self.assertEqual(bill.payments.get().receipt_no, 'Synthetic receipt')

    def test_unrelated_partial_save_does_not_repeat_discount_or_change_snapshot(self):
        bill = self.bill()
        bill.notes = 'Unrelated edit'
        bill.save(update_fields=['notes'])
        bill.refresh_from_db()
        self.assertEqual(bill.rent, Decimal('2000.00'))
        self.assertEqual(bill.holiday_waiver, Decimal('1000.00'))
        self.assertEqual(bill.full_month_rent, Decimal('3000.00'))

    def test_older_exports_without_holiday_fields_keep_their_saved_rent(self):
        from estate_app.data_transfer.serialization import export_data, validate_data

        self.bill()
        data = export_data()
        data['version'] = 1
        for row in data['records']:
            if row['model'] == 'estate_app.bill':
                for field in ['full_month_rent', 'holiday_start_date', 'holiday_end_date',
                              'holiday_closed_days', 'holiday_waiver']:
                    row['fields'].pop(field)
        objects, _ = validate_data(data)
        bill = next(item.object for item in objects if isinstance(item.object, Bill))
        self.assertEqual(bill.rent, Decimal('2000.00'))
        self.assertIsNone(bill.full_month_rent)

    def test_import_rejects_forged_net_rent_or_waiver_evidence(self):
        from estate_app.data_transfer.serialization import export_data, validate_data

        self.bill()
        for field, value in [('rent', '1.00'), ('holiday_closed_days', 1), ('holiday_waiver', '2999.00')]:
            data = export_data()
            row = next(row for row in data['records'] if row['model'] == 'estate_app.bill')
            row['fields'][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_data(data)
