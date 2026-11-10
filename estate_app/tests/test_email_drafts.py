import datetime
from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from estate_app.models import Tenant, Bill, SystemSettings

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailDraftTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('draft-user')
        self.api=APIClient(); self.api.force_authenticate(self.user)
        self.tenant=Tenant.objects.create(name='Example Vendor',email='vendor@example.invalid',type='Shop',penalty_type='none',gst_applicable=False)
        self.bill=Bill.objects.create(tenant=self.tenant,month=1,year=2026,rent=100,due_date=datetime.date(2026,2,1))

    def generate(self, **extra):
        from estate_app.models import EmailTemplate
        template=EmailTemplate.objects.first()
        return self.api.post('/api/email-drafts/generate/',{'allottee_id':self.tenant.pk,'bill_ids':[self.bill.pk],'template_id':template.pk,**extra},format='json')

    def test_three_reusable_templates_and_no_saved_allottee_drafts(self):
        from estate_app.models import EmailTemplate
        self.assertEqual(len(self.api.get('/api/email-templates/').data),3)
        template=EmailTemplate.objects.first();before=(template.subject,template.body)
        for tenant in [self.tenant,Tenant.objects.create(name='Second vendor',type='Shop')]:
            response=self.generate(allottee_id=tenant.pk,bill_ids=[])
            self.assertEqual(response.status_code,200,response.data)
            self.assertIn(tenant.name,response.data['body'])
        template.refresh_from_db();self.assertEqual((template.subject,template.body),before)
        self.assertNotIn('estate_app_emaildraft',connection.introspection.table_names())
        self.assertIn(self.api.post('/api/email-drafts/',{},format='json').status_code,[404,405])
        self.assertEqual(len(getattr(mail,'outbox',[])),0)

    def test_authentication_approval_and_template_write_permissions(self):
        from estate_app.models import AccountAccess
        self.assertEqual(self.api.post('/api/email-templates/',{},format='json').status_code,405)
        self.api.force_authenticate(None)
        self.assertIn(self.api.get('/api/email-templates/').status_code,[401,403])
        self.api.force_authenticate(self.user)
        AccountAccess.objects.create(user=self.user,status='pending')
        self.assertEqual(self.api.get('/api/email-templates/').status_code,403)
        self.assertEqual(self.generate().status_code,403)

    def test_mixed_allottees_and_missing_bills_rejected(self):
        other=Tenant.objects.create(name='Other Vendor',type='Shop')
        bill=Bill.objects.create(tenant=other,month=1,year=2026,rent=10)
        self.assertEqual(self.generate(bill_ids=[self.bill.pk,bill.pk]).status_code,400)
        self.assertEqual(self.generate(bill_ids=[999999]).status_code,400)
        self.assertEqual(self.generate(bill_ids=[self.bill.pk,self.bill.pk]).status_code,400)

    def test_missing_email_and_private_cc(self):
        self.tenant.email='';self.tenant.save()
        config=SystemSettings.get_settings();config.email_draft_cc='authority@example.invalid';config.save()
        draft=self.generate().data
        self.assertEqual(draft['to'],'');self.assertEqual(draft['cc'],'authority@example.invalid')
        self.assertIn('Receipt not confirmed',draft['body'])

    def test_template_placeholders_are_literal_only(self):
        from estate_app.models import EmailTemplate
        for body in ['{unknown}','{allottee_name.__class__}','{allottee_name!r}','{allottee_name:>100}']:
            with self.assertRaises(ValidationError):EmailTemplate(name='Bad',subject='Hello',body=body).full_clean()
        template=EmailTemplate.objects.first();template.body='{{literal}} {allottee_name}';template.save()
        self.assertEqual(self.generate().data['body'],'{literal} Example Vendor')

    def test_expanded_subject_newlines_rejected_before_copy(self):
        from estate_app.models import EmailTemplate
        template=EmailTemplate.objects.first();template.subject='{bill_details}';template.save()
        self.assertEqual(self.generate(template_id=template.pk).status_code,400)

    def test_inactive_template_rejected(self):
        from estate_app.models import EmailTemplate
        template=EmailTemplate.objects.first();template.active=False;template.save()
        self.assertEqual(self.generate(template_id=template.pk).status_code,400)

    def test_bad_headers_and_cc_rejected(self):
        from estate_app.models import EmailTemplate
        config=SystemSettings.get_settings();config.email_draft_cc='not-an-email'
        with self.assertRaises(ValidationError):config.full_clean()
        for cc in ['bad-address','one@example.invalid\nother@example.invalid']:
            config.email_draft_cc=cc
            with self.assertRaises(ValidationError):config.full_clean()
        with self.assertRaises(ValidationError):EmailTemplate(name='Bad',subject='Hello\r\nBcc: bad',body='Hello').full_clean()

    def test_current_partial_paid_and_settled_values(self):
        from estate_app.models import Payment
        Payment.objects.create(bill=self.bill,amount=40,payment_date=datetime.date(2026,1,1))
        self.assertIn('INR 60.00',self.generate().data['body'])
        Payment.objects.create(bill=self.bill,amount=60,payment_date=datetime.date(2026,1,2))
        self.assertIn('INR 0.00',self.generate().data['body'])

    def test_generation_does_not_change_business_records(self):
        from estate_app.models import Payment,ReminderDelivery
        before=list(Bill.objects.values())
        self.assertEqual(self.generate().status_code,200)
        self.assertEqual(list(Bill.objects.values()),before)
        self.assertFalse(Payment.objects.exists());self.assertFalse(ReminderDelivery.objects.exists())

    def test_generation_metadata_and_no_store(self):
        self.assertEqual(self.api.options('/api/email-drafts/generate/').status_code,200)
        self.assertIn('no-store',self.generate()['Cache-Control'])
        self.assertIn('no-store',self.api.get('/api/email-templates/')['Cache-Control'])

    def test_admin_saves_reusable_template_and_rejects_unknown_fields(self):
        from estate_app.models import EmailTemplate
        admin=User.objects.create_superuser('template-admin','admin@example.invalid','Synthetic-template-passphrase-83!')
        self.client.force_login(admin)
        path='/admin/estate_app/emailtemplate/add/'
        response=self.client.post(path,{'name':'Custom covering note','subject':'For {allottee_name}',
                                       'body':'Dear {allottee_name}, {outstanding_total}','active':'on','_save':'Save'})
        self.assertEqual(response.status_code,302)
        template=EmailTemplate.objects.get(name='Custom covering note')
        self.assertEqual(self.generate(template_id=template.pk).data['subject'],'For Example Vendor')
        response=self.client.post(path,{'name':'Invalid','subject':'For {unsupported}',
                                       'body':'Dear {allottee_name}','active':'on','_save':'Save'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(EmailTemplate.objects.filter(name='Invalid').exists())

    def test_merge_includes_current_penalty_and_confirmed_due_date(self):
        from django.utils import timezone
        self.tenant.penalty_type='lumpsum';self.tenant.custom_penalty_lumpsum=25
        self.tenant.custom_penalty_frequency='day';self.tenant.save()
        self.bill.issue_date=timezone.localdate()-datetime.timedelta(days=12);self.bill.save()
        draft=self.generate().data
        self.assertIn('Remaining penalty: INR 175.00',draft['body'])
        self.assertIn('Outstanding: INR 275.00',draft['body'])
        self.assertIn(str(self.bill.due_date),draft['body'])
