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


class GlobalInvoiceSettingsTests(TestCase):
    maxDiff = 1000

    def setUp(self):
        from estate_app.models import SystemSettings
        SystemSettings.objects.update_or_create(pk=1, defaults={'letterhead_name':'Example Organisation'})
        self.settings = SystemSettings.get_settings()
        self.tenant = Tenant.objects.create(name='Settings Tenant', type='Shop', penalty_type='none')
        self.bill = Bill.objects.create(tenant=self.tenant, month=1, year=2026,
                                       rent=Decimal('100.00'), due_date=datetime.date(2026, 2, 1))

    def test_global_text_is_escaped_and_used_in_every_invoice_format(self):
        values = {
            'letterhead_name': 'Custom Institute', 'letterhead_department': 'Custom Division',
            'letterhead_address': 'Custom Campus\nSecond address line',
            'signing_authority': 'First signatory line\nSecond signatory line\nThird signatory line',
            'billed_from': 'Custom sender\nSender address', 'supplier_gstin': 'CUSTOM-GSTIN',
            'place_of_supply': 'Custom State', 'invoice_note': 'Custom note <script>alert(1)</script>\nNext note line',
            'copy_to': 'Custom recipient one\nCustom recipient two',
            'reference_number_format': 'CUSTOM/Pdd/_____/{year}',
            'bank_details': 'Custom Bank\nAccount: 0012345', 'invoice_remarks': 'Custom remarks\nSecond remark',
        }
        for field, value in values.items():
            setattr(self.settings, field, value)
        self.settings.save()
        context = invoice_context(self.bill)
        consolidated = consolidated_invoice_context([self.bill])
        cases = [('invoice_format2.html', context)]
        for template in ('bulk_invoice.html', 'admin/estate_app/bill/bulk_print.html'):
            cases.extend([(template, {'print_invoices': [{'invoice': context, 'consolidated': False}]}),
                          (template, {'print_invoices': [{'invoice': consolidated, 'consolidated': True}]})])
        for template, data in cases:
            with self.subTest(template=template, consolidated=bool(data.get('print_invoices', [{}])[0].get('consolidated'))):
                html = render_to_string(template, data)
                for marker in ('Custom Institute', 'Custom Division', 'Second address line',
                               'First signatory line<br>Second signatory line<br>Third signatory line',
                               'Custom sender<br>Sender address', 'CUSTOM-GSTIN', 'Custom State',
                               'Custom recipient one<br>Custom recipient two', 'CUSTOM/Pdd/_____/2026',
                               'Custom Bank<br>Account: 0012345', 'Custom remarks<br>Second remark'):
                    self.assertTrue(marker in html, f'{template} is missing {marker!r}')
                self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;<br>Next note line', html)
                self.assertNotIn('<script>alert(1)</script>', html)
                self.assertNotIn('00000000000', html)

    def test_saved_reference_is_preserved_and_global_changes_appear_on_reprint(self):
        self.bill.dispatch_ref_no = 'SIGNED/123/2025'
        self.bill.save()
        self.settings.reference_number_format = 'NEW/_____/{year}'
        self.settings.invoice_note = 'Updated global note'
        self.settings.save()
        context = invoice_context(self.bill)
        self.assertEqual(context['dispatch_ref_no'], 'SIGNED/123/2025')
        self.assertIn('Updated global note', render_to_string('invoice_format2.html', context))
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.dispatch_ref_no, 'SIGNED/123/2025')

    def test_admin_saves_multiline_settings_and_embeds_uploaded_logo(self):
        import io
        import tempfile
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        user = User.objects.create_superuser('settings-admin', 'admin@example.invalid', 'test-password')
        self.client.force_login(user)
        response = self.client.get(f'/admin/estate_app/systemsettings/{self.settings.pk}/change/', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current letterhead logo')
        for section in ('Letterhead', 'Billed from', 'Signing authority', 'Payment information'):
            self.assertContains(response, section)
        image = io.BytesIO()
        Image.new('RGB', (12, 12), 'red').save(image, format='PNG')
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            data = model_to_dict(self.settings, exclude=['updated_at', 'updated_by', 'letterhead_logo'])
            data['signing_authority'] = 'Officer\nDivision\nInstitute'
            data['change_reason'] = 'Update signing authority and logo'
            data['letterhead_logo'] = SimpleUploadedFile('custom.png', image.getvalue(), content_type='image/png')
            response = self.client.post(f'/admin/estate_app/systemsettings/{self.settings.pk}/change/',
                                        data, HTTP_HOST='localhost')
            self.assertEqual(response.status_code, 302, response.context and response.context['adminform'].form.errors)
            self.settings.refresh_from_db()
            self.assertEqual(self.settings.updated_by, user)
            html = render_to_string('invoice_format2.html', invoice_context(self.bill))
            self.assertIn('Officer<br>Division<br>Institute', html)
            import base64
            self.assertIn('data:image/png;base64,' + base64.b64encode(image.getvalue()).decode('ascii'), html)

    def test_admin_rejects_non_image_and_oversized_logo(self):
        import io
        from PIL import Image
        from django.contrib import admin
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import RequestFactory
        form_class = admin.site._registry[SystemSettings].get_form(RequestFactory().get('/'))
        content = io.BytesIO()
        Image.new('RGB', (2, 2)).save(content, format='PNG')
        for upload in (SimpleUploadedFile('logo.png', b'not an image'),
                       SimpleUploadedFile('logo.svg', b'<svg/>'),
                       SimpleUploadedFile('large.png', content.getvalue() + b'0' * (2 * 1024 * 1024))):
            with self.subTest(name=upload.name):
                data = model_to_dict(self.settings, exclude=['updated_at', 'updated_by', 'letterhead_logo'])
                form = form_class(data=data, files={'letterhead_logo': upload}, instance=self.settings)
                self.assertFalse(form.is_valid())
                self.assertIn('letterhead_logo', form.errors)

    def test_issue_year_reference_and_missing_logo_fallback(self):
        self.bill.issue_date = datetime.date(2025, 1, 2)
        self.bill.save()
        self.settings.letterhead_logo = 'invoice-branding/missing.png'
        self.settings.save()
        context = invoice_context(self.bill)
        self.assertEqual(context['dispatch_ref_no'], 'REF/_____/2025')
        self.assertTrue(context['invoice_logo'].startswith('data:image/png;base64,'))

    def test_blank_optional_text_and_copy_to_can_be_omitted(self):
        self.settings.copy_to = ''
        self.settings.invoice_note = ''
        self.settings.invoice_remarks = ''
        self.settings.save()
        context = invoice_context(self.bill)
        for template in ('invoice_format2.html',):
            html = render_to_string(template, context)
            self.assertNotIn('Copy to:', html)
            self.assertNotIn('Due date is 5 day', html)
            self.assertNotIn('Cheque / DD in favour', html)
