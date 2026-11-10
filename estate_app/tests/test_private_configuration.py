import datetime
from django.contrib.auth.models import User
from django.test import TestCase
from estate_app.models import SystemSettings, Tenant, Bill

class PrivateConfigurationTests(TestCase):
    def test_fresh_install_contains_no_organisation_profile(self):
        profile=SystemSettings.get_settings()
        for field in ['letterhead_name','letterhead_department','letterhead_address','signing_authority','supplier_gstin','place_of_supply','bank_details','invoice_remarks']:
            self.assertEqual(getattr(profile,field),'',field)

    def test_printing_requires_organisation_name_on_all_routes(self):
        user=User.objects.create_user('reader',password='Synthetic-reader-passphrase-83!')
        self.client.force_login(user)
        tenant=Tenant.objects.create(name='Synthetic Customer',type='Shop',penalty_type='none')
        bill=Bill.objects.create(tenant=tenant,month=1,year=2026,rent=100,due_date=datetime.date(2026,2,1))
        for path in [f'/api/invoice/{bill.pk}/',f'/api/invoice/{bill.pk}/format-2/',f'/api/invoice/bulk/?ids={bill.pk}']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,400,path)
            self.assertIn(b'Configure the organisation name',response.content)

    def test_generic_logo_without_institutional_fallback(self):
        from estate_app.views.invoices.branding import invoice_logo_data_uri
        self.assertTrue(invoice_logo_data_uri(SystemSettings.get_settings()).startswith('data:image/png;base64,'))

    def test_initial_schema_is_fresh_and_does_not_seed_business_or_users(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        self.assertEqual(MigrationLoader(connection).graph.leaf_nodes('estate_app'),[('estate_app','0003_tenant_allotment_description')])
        self.assertFalse(User.objects.exists())
        self.assertFalse(Tenant.objects.exists())
        self.assertFalse(Bill.objects.exists())
        self.assertFalse(SystemSettings.objects.exists())

    def test_admin_and_legacy_pdf_printing_require_configuration(self):
        from django.urls import reverse
        from django.core.exceptions import ValidationError
        from estate_app.pdf_utils import generate_invoice_pdf
        user=User.objects.create_superuser('print-admin','print@example.invalid','Synthetic-print-passphrase-93!')
        self.client.force_login(user)
        tenant=Tenant.objects.create(name='Synthetic Customer',type='Shop',penalty_type='none')
        bill=Bill.objects.create(tenant=tenant,month=1,year=2026,rent=100)
        response=self.client.get(reverse('admin:estate_app_bill_bulk_print'),{'ids':str(bill.pk)})
        self.assertEqual(response.status_code,400)
        self.assertContains(response,'Configure the organisation name',status_code=400)
        with self.assertRaises(ValidationError):generate_invoice_pdf(bill)
