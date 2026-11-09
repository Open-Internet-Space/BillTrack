import csv
import datetime as dt
import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import Bill, Payment, Tenant


class ReportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user('reporter'))
        self.tenant = Tenant.objects.create(name='=Vendor', type='Shop', penalty_type='none', gst_applicable=False)
        self.bill = Bill.objects.create(tenant=self.tenant, year=2026, month=1, rent=100,
                                       issue_date=dt.date(2026, 1, 1), due_date=dt.date(2026, 1, 6))
        Payment.objects.create(bill=self.bill, payment_date=dt.date(2026, 1, 10), amount=30)
        Payment.objects.create(bill=self.bill, payment_date=dt.date(2026, 2, 10), amount=70)

    def report(self, kind='pending', **params):
        return self.client.get('/api/reports/', {'report': kind, 'to': '2026-01-31', **params})

    def test_cutoff_excludes_later_payments_and_counts_bill_once(self):
        data = self.report().json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['totals']['billed'], '100.00')
        self.assertEqual(data['totals']['paid'], '30.00')
        self.assertEqual(data['totals']['balance'], '70.00')

    def test_payments_use_payment_date_and_export_all_rows(self):
        data = self.report('payments', **{'from': '2026-02-01', 'to': '2026-02-28'}).json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['totals']['received'], '70.00')
        response = self.report('payments', to='2026-02-28', output='csv')
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertTrue(any("'=Vendor" in row for row in rows))
        self.assertTrue(any('100.00' in row for row in rows))

    def test_statement_reconciles_opening_and_movements(self):
        data = self.report('statement', **{'from': '2026-02-01', 'to': '2026-02-28'}).json()
        self.assertEqual(data['totals']['opening'], '70.00')
        self.assertEqual(data['totals']['billed'], '0.00')
        self.assertEqual(data['totals']['received'], '70.00')
        self.assertEqual(data['totals']['closing'], '0.00')

    def test_penalty_uses_cutoff_even_when_bill_is_now_settled(self):
        self.tenant.penalty_type = 'percentage'
        self.tenant.custom_penalty_rate = Decimal('36.5')
        self.tenant.save()
        data = self.report('penalties').json()
        self.assertEqual(data['totals']['penalty_accrued'], '1.87')
        self.assertEqual(data['totals']['penalty_due'], '1.87')

    def test_pending_receipt_does_not_accrue_penalty(self):
        self.bill.issue_date = None
        self.bill.save()
        data = self.report().json()
        self.assertEqual(data['rows'][0]['receipt_status'], 'Pending Receipt')
        self.assertEqual(data['totals']['penalty_due'], '0.00')

    def test_invalid_filters_are_rejected(self):
        for params in ({'report': 'unknown'}, {'to': 'bad'}, {'from': '2026-02-01'},
                       {'tenant': 'bad'}, {'status': 'bad'}, {'receipt_status': 'bad'}, {'output': 'bad'}):
            self.assertEqual(self.report(**params).status_code, 400, params)

    def test_reports_require_authentication_including_exports(self):
        self.client.force_authenticate(None)
        for output in ('json', 'csv', 'pdf'):
            self.assertEqual(self.report(output=output).status_code, 401)

    @patch('estate_app.views.reports.HTML')
    def test_pdf_uses_same_report_and_print_headings(self, html):
        html.return_value.write_pdf.return_value = b'%PDF-test'
        response = self.report(output='pdf')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        source = html.call_args.kwargs['string']
        self.assertIn('Pending bills', source)
        self.assertIn('70.00', source)
        self.assertIn('thead', source)

    def test_exports_use_reviewed_snapshot_even_after_payment_changes(self):
        preview = self.report().json()
        Payment.objects.create(bill=self.bill, payment_date=dt.date(2026, 1, 20), amount=20)
        for output in ('xlsx', 'docx'):
            response = self.client.post('/api/reports/', {'snapshot': preview['snapshot'], 'output': output}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b'PK'))
            if output == 'xlsx':
                from openpyxl import load_workbook
                sheet = load_workbook(io.BytesIO(response.content)).active
                cells = [cell for row in sheet for cell in row]
                self.assertTrue(any(cell.value == 70 and cell.data_type == 'n' for cell in cells))
                self.assertTrue(any(cell.value == '=Vendor' and cell.data_type == 's' for cell in cells))
                self.assertFalse(any(cell.data_type == 'f' for cell in cells))
            else:
                from docx import Document
                document = Document(io.BytesIO(response.content))
                text = ' '.join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
                self.assertIn('70.00', text)
                self.assertIn('=Vendor', text)

    def test_export_rejects_tampered_or_other_users_snapshot(self):
        snapshot = self.report().json()['snapshot']
        response = self.client.post('/api/reports/', {'snapshot': snapshot + 'x', 'output': 'xlsx'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(User.objects.create_user('other-reporter'))
        response = self.client.post('/api/reports/', {'snapshot': snapshot, 'output': 'docx'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_statement_preserves_credit_and_penalty_receipts(self):
        Payment.objects.create(bill=self.bill, payment_date=dt.date(2026, 2, 15), amount=10, penalty_paid=5)
        data = self.report('statement', **{'from': '2026-02-01', 'to': '2026-02-28'}).json()
        self.assertEqual(data['totals']['opening'], '70.00')
        self.assertEqual(data['totals']['received'], '85.00')
        self.assertEqual(data['totals']['closing'], '-15.00')

    def test_pending_includes_older_bills_and_uses_cutoff_status(self):
        data = self.report('pending', **{'from': '2026-01-25', 'status': 'Partial'}).json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['rows'][0]['status'], 'Partial')
        self.assertEqual(self.report('pending', status='Paid').json()['count'], 0)

    def test_billing_month_filter_is_separate_from_payment_dates(self):
        data = self.report('payments', **{'from': '2026-02-01', 'to': '2026-02-28', 'billing_from': '2026-01', 'billing_to': '2026-01'}).json()
        self.assertEqual(data['totals']['received'], '70.00')
        self.assertEqual(self.report('payments', billing_from='2026-02').json()['count'], 0)

    def test_empty_reports_have_zero_totals(self):
        data = self.report('payments', **{'from': '2026-01-11', 'to': '2026-01-12'}).json()
        self.assertEqual(data['rows'], [])
        self.assertEqual(data['totals']['received'], '0.00')

    def test_empty_report_exports_all_three_formats(self):
        data = self.report('payments', **{'from': '2026-01-11', 'to': '2026-01-12'}).json()
        for output, signature in [('pdf', b'%PDF'), ('docx', b'PK'), ('xlsx', b'PK')]:
            response = self.client.post('/api/reports/', {'snapshot': data['snapshot'], 'output': output}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(signature))

    def test_bills_register_includes_charge_breakdown_and_payment_status(self):
        data = self.report('bills').json()
        self.assertEqual(data['rows'][0]['status'], 'Partial')
        self.assertIn('status', [column['key'] for column in data['columns']])
        self.assertEqual(data['totals']['rent'], '100.00')

    def test_reports_show_manual_dispatch_reference_instead_of_generated_invoice_number(self):
        self.bill.dispatch_ref_no = 'PDD/REF/2026/42'
        self.bill.save(update_fields=['dispatch_ref_no'])
        for kind in ('pending', 'payments', 'bills'):
            data = self.report(kind).json()
            self.assertEqual(data['rows'][0]['dispatch_ref_no'], 'PDD/REF/2026/42')
            self.assertNotIn('invoice', [column['key'] for column in data['columns']])
        preview = self.report().json()
        for output in ('docx', 'xlsx'):
            response = self.client.post('/api/reports/', {'snapshot': preview['snapshot'], 'output': output}, format='json')
            if output == 'docx':
                from docx import Document
                text = ' '.join(cell.text for table in Document(io.BytesIO(response.content)).tables for row in table.rows for cell in row.cells)
            else:
                from openpyxl import load_workbook
                text = ' '.join(str(cell.value) for row in load_workbook(io.BytesIO(response.content)).active for cell in row)
            self.assertIn('PDD/REF/2026/42', text)
            self.assertNotIn(self.bill.invoice_no, text)
        with patch('estate_app.views.reports.HTML') as html:
            html.return_value.write_pdf.return_value = b'%PDF-test'
            self.client.post('/api/reports/', {'snapshot': preview['snapshot'], 'output': 'pdf'}, format='json')
            source = html.call_args.kwargs['string']
            self.assertIn('PDD/REF/2026/42', source)
            self.assertNotIn(self.bill.invoice_no, source)

    def test_blank_reference_does_not_fall_back_to_generated_invoice(self):
        self.assertEqual(self.report().json()['rows'][0]['dispatch_ref_no'], '')

    def test_bill_date_is_available_in_bill_reports_and_selected_exports(self):
        self.tenant.penalty_type = 'percentage'
        self.tenant.custom_penalty_rate = Decimal('36.5')
        self.tenant.save()
        for kind in ('pending', 'payments', 'penalties', 'bills'):
            data = self.report(kind).json()
            self.assertEqual(data['rows'][0]['bill_date'], '2026-01-01')
            self.assertIn('bill_date', [column['key'] for column in data['columns']])
        snapshot = self.report().json()['snapshot']
        for output in ('docx', 'xlsx', 'pdf'):
            with patch('estate_app.views.reports.HTML') as html:
                html.return_value.write_pdf.return_value = b'%PDF-test'
                response = self.client.post('/api/reports/', {'snapshot': snapshot, 'output': output, 'columns': ['bill_date']}, format='json')
                self.assertEqual(response.status_code, 200)
                if output == 'docx':
                    from docx import Document
                    table = Document(io.BytesIO(response.content)).tables[0]
                    self.assertEqual(table.rows[0].cells[1].text, 'Bill date')
                    self.assertEqual(table.rows[1].cells[1].text, '2026-01-01')
                elif output == 'xlsx':
                    from openpyxl import load_workbook
                    sheet = load_workbook(io.BytesIO(response.content)).active
                    self.assertEqual(sheet.cell(6, 2).value, 'Bill date')
                    self.assertEqual(sheet.cell(7, 2).value, '2026-01-01')
                else:
                    source = html.call_args.kwargs['string']
                    self.assertIn('Bill date', source)
                    self.assertIn('2026-01-01', source)

    def test_bill_date_is_blank_until_receipt_is_confirmed_at_cutoff(self):
        for issue_date in (None, dt.date(2026, 2, 1)):
            self.bill.issue_date = issue_date
            self.bill.save()
            self.assertEqual(self.report().json()['rows'][0]['bill_date'], '')

    def test_downloads_include_only_selected_columns_and_keep_numeric_total(self):
        snapshot = self.report().json()['snapshot']
        body = {'snapshot': snapshot, 'columns': ['balance']}
        for output in ('docx', 'xlsx', 'pdf'):
            with patch('estate_app.views.reports.HTML') as html:
                html.return_value.write_pdf.return_value = b'%PDF-test'
                response = self.client.post('/api/reports/', {**body, 'output': output}, format='json')
                self.assertEqual(response.status_code, 200)
                if output == 'docx':
                    from docx import Document
                    table = Document(io.BytesIO(response.content)).tables[0]
                    self.assertEqual([cell.text for cell in table.rows[0].cells], ['No.', 'Principal due'])
                    self.assertEqual(table.rows[-1].cells[1].text, '70.00')
                    text = ' '.join(cell.text for row in table.rows for cell in row.cells)
                    self.assertNotIn('=Vendor', text)
                elif output == 'xlsx':
                    from openpyxl import load_workbook
                    sheet = load_workbook(io.BytesIO(response.content)).active
                    self.assertEqual(sheet.max_column, 2)
                    self.assertEqual(sheet.cell(6, 2).value, 'Principal due')
                    self.assertEqual(sheet.cell(8, 2).value, 70)
                else:
                    source = html.call_args.kwargs['string']
                    self.assertIn('Principal due', source)
                    self.assertNotIn('=Vendor', source)
                    self.assertNotIn('Reference / dispatch no.', source)
                    self.assertEqual(source.count('70.00'), 2)

    def test_invalid_column_selections_are_rejected(self):
        snapshot = self.report().json()['snapshot']
        for columns in ([], ['unknown'], 'balance', [None], [['balance']], {'balance': True}):
            response = self.client.post('/api/reports/', {'snapshot': snapshot, 'output': 'xlsx', 'columns': columns}, format='json')
            self.assertEqual(response.status_code, 400, columns)

    def test_penalty_only_payment_is_received_and_settles_penalty(self):
        self.tenant.penalty_type = 'percentage'
        self.tenant.custom_penalty_rate = Decimal('36.5')
        self.tenant.save()
        Payment.objects.create(bill=self.bill, payment_date=dt.date(2026, 1, 31), amount=0, penalty_paid=1)
        self.assertEqual(self.report('penalties').json()['totals']['penalty_due'], '0.87')
        self.assertEqual(self.report('payments').json()['totals']['received'], '31.00')

    def test_post_exports_require_auth_and_valid_format(self):
        self.assertEqual(self.client.post('/api/reports/', {'output': 'xlsx'}, format='json').status_code, 400)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/reports/', {'output': 'docx'}, format='json').status_code, 401)

    def test_advance_receipts_are_counted_before_the_billing_month(self):
        future_bill = Bill.objects.create(tenant=self.tenant, year=2026, month=3, rent=100)
        Payment.objects.create(bill=future_bill, payment_date=dt.date(2026, 1, 15), amount=25)
        self.assertEqual(self.report('payments').json()['totals']['received'], '55.00')
        data = self.report('statement', **{'from': '2026-02-01', 'to': '2026-02-28'}).json()
        self.assertEqual(data['totals']['opening'], '45.00')
        self.assertEqual(data['totals']['closing'], '-25.00')

    def test_penalty_days_stop_at_principal_settlement(self):
        self.tenant.penalty_type = 'percentage'
        self.tenant.custom_penalty_rate = Decimal('36.5')
        self.tenant.save()
        data = self.report('penalties', to='2026-02-28').json()
        self.assertEqual(data['rows'][0]['days_overdue'], 35)

    def test_invalid_snapshot_types_and_expiry_are_rejected(self):
        for snapshot in (None, {}, []):
            response = self.client.post('/api/reports/', {'snapshot': snapshot, 'output': 'xlsx'}, format='json')
            self.assertEqual(response.status_code, 400)
        snapshot = self.report().json()['snapshot']
        with patch('django.core.signing.time.time', return_value=9999999999):
            response = self.client.post('/api/reports/', {'snapshot': snapshot, 'output': 'xlsx'}, format='json')
        self.assertEqual(response.status_code, 400)
