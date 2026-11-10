import base64
import copy
import datetime
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from ..models import Bill, Payment, SystemSettings, Tenant


class AdminDataTransferTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(
            MEDIA_ROOT=Path(self.directory.name) / 'media',
            BASE_DIR=Path(self.directory.name),
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create_superuser('transfer-admin', 'admin@example.invalid', 'password')
        self.client.force_login(self.user)
        self.tenant = Tenant.objects.create(name='Original allottee', type='Shop', gst_applicable=False)
        self.bill = Bill.objects.create(tenant=self.tenant, month=12, year=2025, rent=100,
                                        issue_date=datetime.date(2025, 12, 1), created_by=self.user)
        self.payment = Payment.objects.create(bill=self.bill, amount=25,
                                               payment_date=datetime.date(2025, 12, 3), recorded_by=self.user)
        self.config = SystemSettings.get_settings()
        self.config.letterhead_name = 'Exported heading'
        self.config.save()

    def export(self):
        response = self.client.get('/admin/data-transfer/export/')
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def upload(self, data, mode='merge', confirm=True, client=None):
        preview = (client or self.client).get('/admin/data-transfer/')
        return (client or self.client).post('/admin/data-transfer/', {
            'file': SimpleUploadedFile('billtrack.json', json.dumps(data).encode(), 'application/json'),
            'mode': mode, 'confirm': 'on' if confirm else '',
            'change_reason': 'Restore reviewed synthetic records',
            'confirmation': preview.context['replacement_plan']['confirmation'] if preview.status_code == 200 else '',
        }, follow=True)

    def test_replacement_preserves_audit_snapshots_and_requires_reason(self):
        from estate_app.models import ActivityEntry
        exported = self.export()
        response = self.upload(exported, 'replace')
        self.assertContains(response, 'Import completed')
        entries = ActivityEntry.objects.filter(source='import', action='delete')
        self.assertEqual(set(entries.values_list('record_type', flat=True)),
                         {'estate_app.tenant', 'estate_app.bill', 'estate_app.payment', 'estate_app.systemsettings'})
        self.assertEqual(entries.get(record_type='estate_app.payment').actor_name, self.user.username)
        self.assertEqual(entries.get(record_type='estate_app.tenant').before['name'], 'Original allottee')
        count = ActivityEntry.objects.count()
        response = self.client.post('/admin/data-transfer/', {
            'file': SimpleUploadedFile('billtrack.json', json.dumps(exported).encode(), 'application/json'),
            'mode': 'merge'})
        self.assertContains(response, 'This field is required')
        self.assertEqual(ActivityEntry.objects.count(), count)

    def test_export_is_complete_but_excludes_credentials(self):
        data = self.export()
        self.assertEqual(data['format'], 'billtrack-data')
        self.assertEqual(data['version'], 1)
        self.assertEqual({row['model'] for row in data['records']}, {
            'estate_app.tenant', 'estate_app.bill', 'estate_app.payment', 'estate_app.systemsettings',
        })
        self.assertNotIn('password', json.dumps(data))
        bill = next(row for row in data['records'] if row['model'] == 'estate_app.bill')
        self.assertEqual(bill['fields']['created_by'], self.user.username)
        self.assertIn('uuid', next(row for row in data['records'] if row['model'] == 'estate_app.payment')['fields'])

    def test_legacy_long_invoice_number_round_trips_unchanged(self):
        number = 'HISTORICAL-ALLOTMENT-REFERENCE/2025/DECEMBER/INVOICE-000001'
        Bill.objects.filter(pk=self.bill.pk).update(invoice_no=number)
        self.assertContains(self.upload(self.export(), 'replace'), 'Import completed')
        self.assertEqual(Bill.objects.get(tenant__uuid=self.tenant.uuid).invoice_no, number)

    def test_replace_restores_historical_fields_and_offers_safety_backup(self):
        # These stored historical values must survive without recalculating using today's settings.
        Bill.objects.filter(pk=self.bill.pk).update(gst_on_rent=18, cgst_on_rent=9, sgst_on_rent=9,
                                                  due_date=datetime.date(2025, 12, 20))
        exported = self.export()
        Tenant.objects.filter(pk=self.tenant.pk).update(name='Before restore')
        extra = Tenant.objects.create(name='Remove on replace', type='Office')
        response = self.upload(exported, 'replace')
        self.assertContains(response, 'Import completed')
        self.assertFalse(Tenant.objects.filter(pk=extra.pk).exists())
        restored = Bill.objects.get(tenant__uuid=self.tenant.uuid)
        self.assertEqual(restored.gst_on_rent, 18)
        self.assertEqual(restored.due_date, datetime.date(2025, 12, 20))
        self.assertEqual(restored.payments.count(), 1)
        self.assertEqual(restored.status, 'Partial')
        self.assertTrue(User.objects.get(pk=self.user.pk).is_superuser)
        backup_url = response.context['backup_url']
        backup = self.client.get(backup_url)
        saved = json.loads(b''.join(backup.streaming_content))
        names = [row['fields'].get('name') for row in saved['records']]
        self.assertIn('Before restore', names)
        self.assertIn('Remove on replace', names)

    def test_merge_preserves_existing_values_and_is_idempotent_with_id_collisions(self):
        exported = self.export()
        for row in exported['records']:
            row['pk'] += 1000
            for field in ('tenant', 'bill'):
                if field in row['fields']:
                    row['fields'][field] += 1000
        Tenant.objects.filter(pk=self.tenant.pk).update(name='Keep local edit')
        self.config.letterhead_name = 'Keep local heading'
        self.config.save()
        extra = Tenant.objects.create(name='Keep local allottee', type='Office')
        for _ in range(2):
            self.assertContains(self.upload(exported), 'Import completed')
        self.assertEqual(Tenant.objects.get(uuid=self.tenant.uuid).name, 'Keep local edit')
        self.assertTrue(Tenant.objects.filter(pk=extra.pk).exists())
        self.assertEqual(Bill.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(SystemSettings.get_settings().letterhead_name, 'Keep local heading')

    def test_merge_adds_new_records_and_remaps_relations(self):
        exported = self.export()
        Payment.objects.all().delete()
        Bill.objects.all().delete()
        Tenant.objects.all().delete()
        local = Tenant.objects.create(name='Local unrelated', type='Office')
        self.assertContains(self.upload(exported), 'Import completed')
        restored = Bill.objects.get(tenant__uuid=self.tenant.uuid)
        self.assertNotEqual(restored.tenant_id, local.pk)
        self.assertEqual(restored.payments.get().uuid, self.payment.uuid)

    def test_merge_adds_missing_payment_to_existing_bill_and_updates_status(self):
        exported = self.export()
        Payment.objects.create(bill=self.bill, amount=75, payment_date=datetime.date(2025, 12, 3))
        Payment.objects.filter(pk=self.payment.pk).delete()
        self.bill.update_status()
        self.assertEqual(Bill.objects.get(pk=self.bill.pk).status, 'Partial')
        for _ in range(2):
            self.assertContains(self.upload(exported), 'Import completed')
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount_paid, 100)
        self.assertEqual(self.bill.status, 'Paid')
        self.assertEqual(self.bill.payments.count(), 2)

    def test_invalid_references_and_fields_cannot_partially_replace_data(self):
        original = self.export()
        for change in ('reference', 'negative', 'unknown_model', 'missing_fields', 'unknown_field', 'duplicate'):
            data = copy.deepcopy(original)
            bill = next(row for row in data['records'] if row['model'] == 'estate_app.bill')
            if change == 'reference':
                bill['fields']['tenant'] = 987654
            elif change == 'negative':
                bill['fields']['rent'] = '-1.00'
            elif change == 'unknown_model':
                bill['model'] = 'auth.user'
            elif change == 'missing_fields':
                del bill['fields']['rent']
            elif change == 'unknown_field':
                bill['fields']['unexpected'] = 'ignored data would be unsafe'
            else:
                data['records'].append(copy.deepcopy(bill))
            with self.subTest(change=change):
                self.assertContains(self.upload(data, 'replace'), 'errorlist')
                self.assertEqual(Bill.objects.get(pk=self.bill.pk).rent, 100)
                self.assertTrue(Tenant.objects.filter(pk=self.tenant.pk).exists())

    def test_invoice_collision_rolls_back_merge(self):
        exported = self.export()
        new = Tenant.objects.create(name='Conflicting invoice', type='Shop', gst_applicable=False)
        Payment.objects.all().delete()
        Bill.objects.all().delete()
        self.tenant.delete()
        Bill.objects.create(tenant=new, month=1, year=2026, rent=10, invoice_no=self.bill.invoice_no)
        response = self.upload(exported)
        self.assertContains(response, 'errorlist')
        self.assertEqual(Bill.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertFalse(Tenant.objects.filter(uuid=self.tenant.uuid).exists())

    def test_replace_requires_confirmation_and_both_modes_are_visible(self):
        self.assertContains(self.client.get('/admin/'), 'Export / import')
        page = self.client.get('/admin/data-transfer/')
        self.assertContains(page, 'Replace all data and settings')
        self.assertContains(page, 'Merge into existing data')
        self.assertContains(self.upload(self.export(), 'replace', confirm=False), 'errorlist')
        self.assertEqual(Bill.objects.count(), 1)

    def test_only_superusers_can_transfer_and_post_is_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/admin/data-transfer/', {'mode': 'replace'}).status_code, 403)
        staff = User.objects.create_user('ordinary-staff', is_staff=True)
        self.client.force_login(staff)
        for url in ('/admin/data-transfer/', '/admin/data-transfer/export/'):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_logo_round_trip_and_invalid_logo_is_rejected(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2), 'blue').save(stream, format='PNG')
        self.config.letterhead_logo = SimpleUploadedFile('logo.png', stream.getvalue(), 'image/png')
        self.config.save()
        exported = self.export()
        self.assertEqual(base64.b64decode(exported['logo']['content']), stream.getvalue())
        self.assertContains(self.upload(exported, 'replace'), 'Import completed')
        with SystemSettings.get_settings().letterhead_logo.open('rb') as logo:
            self.assertEqual(logo.read(), stream.getvalue())
        exported['logo']['content'] = base64.b64encode(b'not an image').decode()
        self.assertContains(self.upload(exported, 'replace'), 'errorlist')
        self.assertEqual(Payment.objects.count(), 1)

    def test_malformed_and_unsupported_files_are_rejected(self):
        for data in ({}, [], {'format': 'billtrack-data', 'version': 999}, self.export() | {'logo': {'content': '!'}}):
            self.assertContains(self.upload(data), 'errorlist')
        response = self.client.post('/admin/data-transfer/', {
            'mode': 'replace', 'confirm': 'on', 'file': SimpleUploadedFile('broken.json', b'{'),
        })
        self.assertContains(response, 'errorlist')
        self.assertEqual(Payment.objects.count(), 1)

    def test_invalid_money_and_identifiers_are_form_errors(self):
        original = self.export()
        for model, field, value in (
            ('estate_app.bill', 'rent', 'NaN'),
            ('estate_app.bill', 'rent', 'Infinity'),
            ('estate_app.tenant', 'uuid', None),
            ('estate_app.bill', 'tenant', True),
            ('estate_app.systemsettings', 'letterhead_logo', '../../private-file'),
        ):
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(original)
                next(row for row in data['records'] if row['model'] == model)['fields'][field] = value
                self.assertContains(self.upload(data, 'replace'), 'errorlist')
                self.assertEqual(Payment.objects.count(), 1)

    def test_file_size_limit_and_private_backup_access(self):
        with patch('estate_app.data_transfer.views.MAX_IMPORT_SIZE', 10):
            self.assertContains(self.upload(self.export()), 'smaller than 25 MB')
        response = self.upload(self.export())
        backup_url = response.context['backup_url']
        self.client.force_login(User.objects.create_user('backup-staff', is_staff=True))
        self.assertEqual(self.client.get(backup_url).status_code, 403)

    def test_logo_storage_failure_rolls_back_replacement(self):
        exported = self.export()
        stream = io.BytesIO()
        Image.new('RGB', (2, 2), 'blue').save(stream, format='PNG')
        exported['logo'] = {'name': 'logo.png', 'content': base64.b64encode(stream.getvalue()).decode()}
        storage = SystemSettings._meta.get_field('letterhead_logo').storage
        with patch.object(storage, 'save', side_effect=OSError('Disk full')):
            self.assertContains(self.upload(exported, 'replace'), 'errorlist')
        self.assertEqual(Payment.objects.get(pk=self.payment.pk).amount, 25)
        self.assertEqual(SystemSettings.get_settings().letterhead_name, 'Exported heading')

    def test_missing_user_is_blank_and_historical_values_survive_merge(self):
        exported = self.export()
        bill = next(row for row in exported['records'] if row['model'] == 'estate_app.bill')
        bill['fields'].update(created_by='absent-on-this-installation', gst_on_rent='18.00',
                              cgst_on_rent='9.00', sgst_on_rent='9.00', due_date='2025-12-20')
        Payment.objects.all().delete()
        Bill.objects.all().delete()
        self.assertContains(self.upload(exported), 'Import completed')
        restored = Bill.objects.get(tenant=self.tenant)
        self.assertIsNone(restored.created_by)
        self.assertEqual(restored.gst_on_rent, 18)
        self.assertEqual(restored.due_date, datetime.date(2025, 12, 20))
        self.assertEqual(User.objects.count(), 1)
