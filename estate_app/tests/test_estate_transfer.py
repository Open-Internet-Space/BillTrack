import copy
import datetime as dt
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from estate_app.data_transfer.serialization import export_bytes,export_data,validate_data
from estate_app.models import Allotment,Bill,Payment,RentRevision,SecurityMovement
from estate_app.tests.test_estate_charges import assessed_charge,charge_term,settle_extension_fee


class EstateTransferTests(TestCase):
    def setUp(self):
        self.enterContext(patch('django.utils.timezone.localdate',return_value=dt.date(2026,11,13)))
        self.boss=User.objects.create_superuser('estate-transfer-reviewer',password='Not exported')
        self.term=charge_term()
        settle_extension_fee(self.term)
        self.renewal=Allotment.objects.create(shop=self.term.shop,tenant=self.term.tenant,source_notice='368/2025',
            award_reference='Synthetic extension',letter_issued_on=dt.date(2026,11,1),start_date=dt.date(2027,1,1),
            end_date=dt.date(2027,12,31),actual_area=150,measurement_reference='Retained measured area',renewal_of=self.term,
            approval_reference='Actual extension approval',performance_reference='Satisfactory review')
        RentRevision.objects.create(original_award=self.term,effective_date=dt.date(2026,4,1),rate=20,
            approval_reference='Already revised April rate',reason='Reviewed accepted rate basis')
        self.bill=Bill.objects.create(tenant=self.term.tenant,allotment=self.term,billing_category='allotment',
            billing_policy='notices_368_369',month=11,year=2026,rent=3000,full_month_rent=3000,electric=0,water=0,
            raised_date=dt.date(2026,11,1),created_by=self.boss)
        Payment.objects.create(bill=self.bill,amount=100,payment_date=dt.date(2026,11,2),receipt_no='Actual cash receipt',recorded_by=self.boss)
        item=self.term.requirements.get(kind='police')
        item.submitted_on=dt.date(2026,1,20);item.submission_reference='Actual police submission'
        item.verified_on=dt.date(2026,1,21);item.verified_by=self.boss;item.save()
        self.charge=assessed_charge(self.term)
        SecurityMovement.objects.create(original_award=self.term,kind='received',amount=5400,effective_date=dt.date(2026,11,1),
            reference='Actual security DD',reason='Actual deposit received',recorded_by=self.boss)
        api=APIClient();api.force_authenticate(self.boss)
        url=f'/api/estate-security/{self.term.pk}/'
        preview=api.post(url+'decision-preview/',dict(action='apply_charge',charge=self.charge.pk,amount='400',
            effective_date='2026-11-13',reference='Approved deposit application',reason='Actual reviewed charge settlement'),format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        confirmed=api.post(url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(confirmed.status_code,200,confirmed.data)

    def test_v2_export_contains_the_complete_estate_graph_and_usernames(self):
        data=export_data()
        self.assertEqual(data['version'],2)
        self.assertEqual({record['model'] for record in data['records']},{'estate_app.'+name for name in (
            'tenant','shop','allotment','allotmentrequirement','rentrevision','bill','payment','estatecharge',
            'estatechargepayment','securitymovement','systemsettings')})
        movement=next(row for row in data['records'] if row['model']=='estate_app.securitymovement')
        self.assertEqual(movement['fields']['recorded_by'],self.boss.username)
        requirement=next(row for row in data['records'] if row['model']=='estate_app.allotmentrequirement' and row['fields']['verified_on'])
        self.assertEqual(requirement['fields']['verified_by'],self.boss.username)
        self.assertNotIn('Not exported',str(data))
        objects,_=validate_data(data)
        self.assertEqual(len(objects),len(data['records']))

    def test_missing_shop_or_settlement_target_is_rejected_before_restore(self):
        for label in ('estate_app.shop','estate_app.estatecharge'):
            data=copy.deepcopy(export_data())
            data['records']=[row for row in data['records'] if row['model']!=label]
            with self.subTest(label=label),self.assertRaises(ValidationError):
                validate_data(data)

    def test_v1_cannot_claim_a_complete_linked_estate_export(self):
        data=export_data();data['version']=1
        data['records']=[row for row in data['records'] if row['model'] in (
            'estate_app.tenant','estate_app.bill','estate_app.payment','estate_app.systemsettings')]
        with self.assertRaises(ValidationError):
            validate_data(data)

    def test_replace_round_trips_the_complete_estate_graph_without_recalculating_money(self):
        from estate_app.data_transfer.restoration import restore_data
        data=export_data()
        objects,logo=validate_data(data)
        restore_data(objects,logo,'replace')
        self.assertEqual(export_data()['records'],data['records'])

    def test_merge_remaps_colliding_ids_and_is_idempotent(self):
        from estate_app.data_transfer.restoration import restore_data
        from estate_app.data_transfer.serialization import MODELS,MODEL_MAP
        data=export_data();before=copy.deepcopy(data['records'])
        for row in data['records']:
            row['pk']+=1000
            for field in MODEL_MAP[row['model']]._meta.fields:
                if field.is_relation and field.remote_field.model in MODELS and row['fields'][field.name] is not None:
                    row['fields'][field.name]+=1000
        for _ in range(2):
            objects,logo=validate_data(data)
            result=restore_data(objects,logo,'merge')
            self.assertEqual(result['added'],0)
            self.assertEqual(export_data()['records'],before)

    def test_merge_adds_full_graph_beside_unrelated_local_id_collisions(self):
        from estate_app.data_transfer.restoration import clear_business_records,restore_data
        from estate_app.models import Shop,Tenant
        data=export_data();tenant_uuid=self.term.tenant.uuid;shop_uuid=self.term.shop.uuid
        clear_business_records()
        local=Tenant.objects.create(pk=self.term.tenant_id,name='Unrelated retained person',type='Shop')
        Shop.objects.create(pk=self.term.shop_id,code='LOCAL-ONLY',name='Retained shop',category='utility')
        objects,logo=validate_data(data)
        result=restore_data(objects,logo,'merge')
        self.assertEqual(result['added'],len(data['records']))
        self.assertTrue(Tenant.objects.filter(pk=local.pk,uuid=local.uuid).exists())
        self.assertTrue(Shop.objects.filter(uuid=shop_uuid).exists())
        restored=Bill.objects.get(invoice_no=self.bill.invoice_no)
        self.assertEqual(restored.tenant.uuid,tenant_uuid)
        self.assertEqual(restored.allotment.uuid,self.term.uuid)
        self.assertEqual(restored.payments.get().amount,100)
        self.assertEqual(SecurityMovement.objects.get(kind='applied').applied_charge.balance_due,Decimal('600'))

    def test_restore_keeps_settings_at_the_active_singleton_id(self):
        from estate_app.data_transfer.restoration import clear_business_records, restore_data
        from estate_app.models import SystemSettings

        settings = SystemSettings.get_settings()
        settings.letterhead_name = 'Restored letterhead'
        settings.save()
        data = export_data()
        for row in data['records']:
            if row['model'] == SystemSettings._meta.label_lower:
                row['pk'] = 42
        for mode in ('merge', 'replace'):
            with self.subTest(mode=mode):
                clear_business_records()
                objects, logo = validate_data(data)
                restore_data(objects, logo, mode)
                self.assertEqual(SystemSettings.get_settings().letterhead_name, 'Restored letterhead')
                self.assertEqual(list(SystemSettings.objects.values_list('pk', flat=True)), [1])

    def test_conflicting_retained_renewal_or_movement_rejects_before_writes(self):
        import uuid
        from estate_app.data_transfer.restoration import restore_data
        from estate_app.models import ActivityEntry
        before=export_data()['records'];count=ActivityEntry.objects.count()
        for case in ('renewal','movement'):
            data=copy.deepcopy(export_data())
            if case=='renewal':
                next(row for row in data['records'] if row['model']=='estate_app.allotment' and row['fields']['renewal_of'])['fields']['uuid']=str(uuid.uuid4())
            else:
                next(row for row in data['records'] if row['model']=='estate_app.securitymovement' and row['fields']['kind']=='received')['fields']['amount']='5500'
            objects,logo=validate_data(data)
            with self.subTest(case=case),self.assertRaises(ValidationError):restore_data(objects,logo,'merge')
            self.assertEqual(export_data()['records'],before)
            self.assertEqual(ActivityEntry.objects.count(),count)

    def test_mid_restore_failure_rolls_back_estate_records_and_audit(self):
        from django.core.serializers.base import DeserializedObject
        from estate_app.data_transfer.restoration import restore_data
        from estate_app.models import ActivityEntry
        data=export_data();before=data['records'];count=ActivityEntry.objects.count()
        objects,logo=validate_data(data)
        save=DeserializedObject.save
        def fail_on_application(item,*args,**kwargs):
            if isinstance(item.object,SecurityMovement) and item.object.kind=='applied':
                raise ValidationError('Synthetic failure after dependency writes')
            return save(item,*args,**kwargs)
        with patch.object(DeserializedObject,'save',new=fail_on_application),self.assertRaises(ValidationError):
            restore_data(objects,logo,'replace')
        self.assertEqual(export_data()['records'],before)
        self.assertEqual(ActivityEntry.objects.count(),count)

    def test_replacement_review_covers_estate_records_and_rejects_changed_deposit_evidence(self):
        from estate_app.data_transfer.views import replacement_plan
        from estate_app.activity.deletion import confirmed
        before=replacement_plan()
        self.assertTrue(any('security movement' in row.lower() for row in before['affected']))
        self.assertTrue(any('allotment' in row.lower() for row in before['affected']))
        SecurityMovement.objects.create(original_award=self.term,kind='received',amount=100,
            effective_date=dt.date(2026,11,13),reference='New actual deposit receipt',reason='New evidence after review',recorded_by=self.boss)
        self.assertFalse(confirmed(before['confirmation'],replacement_plan()))

    def test_admin_replacement_restores_estate_and_saves_complete_private_backup(self):
        import json,tempfile
        from pathlib import Path
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.boss)
        data=export_data()
        with tempfile.TemporaryDirectory() as directory,override_settings(BASE_DIR=Path(directory),MEDIA_ROOT=Path(directory)/'media'):
            page=self.client.get('/admin/data-transfer/')
            response=self.client.post('/admin/data-transfer/',{'mode':'replace','confirm':'on',
                'change_reason':'Restore reviewed synthetic estate graph',
                'confirmation':page.context['replacement_plan']['confirmation'],
                'file':SimpleUploadedFile('estate-v2.json',export_bytes(),'application/json')},follow=True)
            self.assertContains(response,'Import completed')
            self.assertEqual(export_data()['records'],data['records'])
            backups=list((Path(directory)/'backups'/'admin-imports').glob('*.json'))
            self.assertEqual(len(backups),1)
            saved=json.loads(backups[0].read_text())
            self.assertEqual(saved['version'],2)
            self.assertTrue(any(row['model']=='estate_app.securitymovement' for row in saved['records']))

    def test_invalid_estate_relationships_and_financial_graphs_are_rejected(self):
        for case in ('cycle','overlap','missing_approval','fee_amount','missing_renewal_fee','charge_overpayment','negative_held','missing_pair',
                     'duplicate_operation','bill_owner','rate_progression','missing_rate_snapshot'):
            data=copy.deepcopy(export_data())
            rows=data['records']
            root=next(row for row in rows if row['model']=='estate_app.allotment' and row['fields']['renewal_of'] is None)
            renewal=next(row for row in rows if row['model']=='estate_app.allotment' and row['fields']['renewal_of'])
            if case=='cycle':root['fields']['renewal_of']=renewal['pk']
            elif case=='overlap':renewal['fields']['start_date']='2026-12-01'
            elif case=='missing_approval':renewal['fields']['approval_reference']=''
            elif case=='fee_amount':
                next(row for row in rows if row['model']=='estate_app.estatecharge' and row['fields']['kind']=='extension_fee')['fields']['net_amount']='900'
            elif case=='missing_renewal_fee':
                data['records']=[row for row in rows if not (row['model']=='estate_app.estatecharge' and row['fields']['kind']=='extension_fee')]
            elif case=='charge_overpayment':
                next(row for row in rows if row['model']=='estate_app.estatechargepayment' and row['fields']['source']=='security_application')['fields']['amount']='1200'
            elif case=='negative_held':
                next(row for row in rows if row['model']=='estate_app.securitymovement' and row['fields']['kind']=='received')['fields']['amount']='100'
            elif case=='missing_pair':
                data['records']=[row for row in rows if not (row['model']=='estate_app.estatechargepayment' and row['fields']['source']=='security_application')]
            elif case=='bill_owner':
                import uuid
                person=copy.deepcopy(next(row for row in rows if row['model']=='estate_app.tenant'))
                person['pk']=9999;person['fields']['uuid']=str(uuid.uuid4());rows.append(person)
                next(row for row in rows if row['model']=='estate_app.bill')['fields']['tenant']=9999
            elif case=='rate_progression':
                import uuid
                rate=copy.deepcopy(next(row for row in rows if row['model']=='estate_app.rentrevision'))
                rate['pk']=9999;rate['fields'].update(uuid=str(uuid.uuid4()),effective_date='2027-04-01',rate='99.0000');rows.append(rate)
            elif case=='missing_rate_snapshot':
                next(row for row in rows if row['model']=='estate_app.bill')['fields']['rate_snapshot']=None
            else:
                import uuid
                duplicate=copy.deepcopy(next(row for row in rows if row['model']=='estate_app.estatechargepayment' and row['fields']['source']=='security_application'))
                duplicate['pk']=9999;duplicate['fields']['uuid']=str(uuid.uuid4());rows.append(duplicate)
            with self.subTest(case=case),self.assertRaises(ValidationError):
                validate_data(data)
