from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from estate_app.models import Tenant, Bill, Payment, EmailTemplate, SystemSettings
from estate_app.serializers import TenantSerializer, BillListSerializer, PaymentSerializer

class AllotmentDescriptionTests(TestCase):
    def test_description_distinguishes_same_name_without_changing_name(self):
        first=Tenant.objects.create(name='Same Person',type='Shop',allotment_description='Shop 12')
        second=Tenant.objects.create(name='Same Person',type='Shop',allotment_description='Shop 34')
        self.assertEqual(first.name,second.name)
        self.assertEqual(str(first),'Same Person — Shop 12')
        self.assertNotEqual(str(first),str(second))
        serialized=TenantSerializer(first).data
        self.assertEqual(serialized['allotment_description'],'Shop 12')
        self.assertEqual(serialized['display_name'],'Same Person — Shop 12')
        first.allotment_description='';first.save();self.assertEqual(str(first),'Same Person')

    def test_api_save_search_and_validation(self):
        api=APIClient();api.force_authenticate(User.objects.create_user('description-reader'))
        response=api.post('/api/tenants/',{'name':'Same Person','type':'Shop','allotment_description':'Shop 12'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        tenant=Tenant.objects.get(pk=response.data['id']);self.assertEqual(tenant.allotment_description,'Shop 12')
        self.assertEqual(api.get('/api/tenants/?search=Shop%2012').data['count'],1)
        for value in ['x'*201,'Shop 12\nShop 13']:
            self.assertEqual(api.patch(f'/api/tenants/{tenant.pk}/',{'allotment_description':value},format='json').status_code,400)

    def test_bill_and_payment_labels_do_not_replace_legal_name(self):
        tenant=Tenant.objects.create(name='Same Person',type='Shop',allotment_description='Shop 12')
        bill=Bill.objects.create(tenant=tenant,month=1,year=2026,rent=100)
        payment=Payment.objects.create(bill=bill,amount=10)
        data=BillListSerializer(bill).data
        self.assertEqual(data['tenant_name'],'Same Person')
        self.assertEqual(data['tenant_display_name'],'Same Person — Shop 12')
        data=PaymentSerializer(payment).data
        self.assertEqual(data['bill_tenant_name'],'Same Person')
        self.assertEqual(data['bill_tenant_display_name'],'Same Person — Shop 12')

    def test_description_round_trip_and_older_exports(self):
        from estate_app.data_transfer.serialization import export_data, validate_data
        from estate_app.data_transfer.restoration import restore_data
        Tenant.objects.create(name='Same Person',type='Shop',allotment_description='Shop 12')
        SystemSettings.get_settings()
        data=export_data();objects,logo=validate_data(data);restore_data(objects,logo,'replace')
        self.assertEqual(Tenant.objects.get().allotment_description,'Shop 12')
        data['version']=1
        for record in data['records']:
            if record['model']=='estate_app.tenant':record['fields'].pop('allotment_description')
            if record['model']=='estate_app.systemsettings':record['fields'].pop('email_draft_cc',None)
        objects,logo=validate_data(data);restore_data(objects,logo,'replace')
        self.assertEqual(Tenant.objects.get().allotment_description,'')

    def test_template_picker_and_merge_description(self):
        user=User.objects.create_superuser('picker-admin','picker@example.invalid','Synthetic-picker-passphrase-83!')
        self.client.force_login(user)
        response=self.client.get('/admin/estate_app/emailtemplate/add/')
        self.assertContains(response,'Insert placeholder')
        self.assertContains(response,'Allotment description')
        from django.templatetags.static import static
        self.assertContains(response, static('estate_app/email_template_placeholders.js'))
        tenant=Tenant.objects.create(name='Same Person',type='Shop',allotment_description='Shop 12')
        template=EmailTemplate.objects.create(name='Description',subject='{allottee_name}',body='{allotment_description}')
        from estate_app.email_drafts.service import generate
        self.assertEqual(generate(tenant.pk,[],template)['body'],'Shop 12')
