import datetime as dt
from decimal import Decimal
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from estate_app.models import Allotment, Shop, Tenant
from estate_app.tests.transaction_case import ActivityTransactionTestCase


def charge_term():
    return Allotment.objects.create(
        shop=Shop.objects.create(code='CHARGE-101',name='Synthetic charge shop',category='utility'),
        tenant=Tenant.objects.create(name='Charge workflow example',type='Shop'),source_notice='368/2025',
        award_reference='Synthetic charge award',letter_issued_on=dt.date(2026,1,1),
        start_date=dt.date(2026,1,1),end_date=dt.date(2026,12,31),actual_area=150,
        measurement_reference='Synthetic measured area')


def settle_extension_fee(term):
    from django.utils import timezone
    Charge=apps.get_model('estate_app','EstateCharge')
    Receipt=apps.get_model('estate_app','EstateChargePayment')
    day=min(timezone.localdate(),term.end_date)
    fee=Charge.objects.create(allotment=term,kind='extension_fee',description='Synthetic notified extension fee',
        assessed_on=day,authority_reference='Synthetic extension fee assessment',net_amount=Decimal('1000'),
        tax_amount=Decimal('0'),due_date=day)
    Receipt.objects.create(charge=fee,amount=Decimal('1000'),payment_date=day,
                           receipt_reference='Synthetic settled extension fee')
    return fee


def assessed_charge(term,**changes):
    return apps.get_model('estate_app','EstateCharge').objects.create(**{**dict(allotment=term,kind='incident_fine',
        description='Assessed incident with recorded authority',assessed_on=dt.date(2026,11,1),
        authority_reference='Approved decision REF-1',net_amount=Decimal('1000'),tax_amount=Decimal('0'),
        due_date=dt.date(2026,11,10)),**changes})


class EstateChargeTests(TestCase):
    def setUp(self):
        self.assertIn('estatecharge',apps.all_models['estate_app'],'One-off estate charges are not implemented yet')
        self.Charge=apps.get_model('estate_app','EstateCharge')
        self.Receipt=apps.get_model('estate_app','EstateChargePayment')
        self.enterContext(patch('django.utils.timezone.localdate',return_value=dt.date(2026,11,13)))
        self.term=charge_term()

    def charge(self,**changes):
        return assessed_charge(self.term,**changes)

    def receipt(self,charge,**changes):
        return self.Receipt.objects.create(**{**dict(charge=charge,amount=Decimal('400'),
            payment_date=dt.date(2026,11,2),receipt_reference='Synthetic receipt REF-1'),**changes})

    def renewal(self):
        return Allotment.objects.create(shop=self.term.shop,tenant=self.term.tenant,source_notice='368/2025',
            award_reference='Synthetic approved extension',letter_issued_on=dt.date(2026,11,13),
            start_date=dt.date(2027,1,1),end_date=dt.date(2027,12,31),actual_area=150,
            measurement_reference='Retained measurement',renewal_of=self.term,
            performance_reference='Satisfactory performance review',approval_reference='Extension approval REF-1')

    def test_assessments_need_explicit_tax_authority_and_valid_dates(self):
        for changes in [dict(tax_amount=None),dict(tax_amount=Decimal('-1')),dict(net_amount=Decimal('-1')),
                        dict(authority_reference=''),dict(description=''),dict(assessed_on=dt.date(2026,11,14)),
                        dict(due_date=dt.date(2026,10,31)),dict(net_amount=0,tax_amount=0)]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                self.charge(**changes)
        charge=self.charge()
        self.assertEqual(charge.tax_amount,Decimal('0'))
        self.assertEqual(charge.gross_amount,Decimal('1000'))

    def test_partial_receipts_reduce_only_this_charge_without_automatic_interest(self):
        charge=self.charge(tax_amount=Decimal('180'))
        self.receipt(charge)
        charge.refresh_from_db()
        self.assertEqual(charge.amount_paid,Decimal('400'))
        self.assertEqual(charge.balance_due,Decimal('780'))
        self.assertEqual(charge.status,'Partial')
        self.assertTrue(charge.overdue)
        with patch('django.utils.timezone.localdate',return_value=dt.date(2026,12,31)):
            self.assertEqual(charge.balance_due,Decimal('780'))

    def test_receipts_cannot_overpay_or_claim_unpaired_security_application(self):
        charge=self.charge()
        self.receipt(charge,amount=Decimal('600'))
        for changes in [dict(amount=Decimal('500')),dict(amount=0),dict(receipt_reference=''),
                        dict(payment_date=dt.date(2026,10,31)),dict(payment_date=dt.date(2026,11,14)),
                        dict(source='security_application')]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                self.receipt(charge,**changes)
        self.assertEqual(charge.payments.count(),1)

    def test_original_assessment_and_waivers_cannot_be_changed_by_ordinary_saves(self):
        charge=self.charge()
        charge.net_amount=Decimal('500')
        with self.assertRaises(ValidationError):
            charge.save()
        charge.refresh_from_db()
        charge.waiver_amount=Decimal('100')
        with self.assertRaises(ValidationError):
            charge.save()
        self.assertEqual(self.Charge.objects.get(pk=charge.pk).net_amount,Decimal('1000'))

    def test_notice_renewal_requires_assessed_and_settled_extension_fee(self):
        with self.assertRaises(ValidationError):
            self.renewal()
        fee=self.charge(kind='extension_fee',description='Notified extension fee')
        with self.assertRaises(ValidationError):
            self.renewal()
        self.receipt(fee,amount=Decimal('1000'))
        renewal=self.renewal()
        fee.refresh_from_db()
        self.assertEqual(fee.renewal_term_id,renewal.pk)
        self.assertEqual(fee.balance_due,0)
        with self.assertRaises(ValidationError):
            self.charge(kind='extension_fee',description='Duplicate fee')

    def test_notified_fee_and_financial_identity_are_protected(self):
        with self.assertRaises(ValidationError):
            self.charge(kind='extension_fee',net_amount=Decimal('500'))
        self.charge()
        self.term.tenant=Tenant.objects.create(name='Wrong replacement person',type='Shop')
        with self.assertRaises(ValidationError):
            self.term.save()
        self.term.shop.code='MOVED-CODE'
        with self.assertRaises(ValidationError):
            self.term.shop.save()

    def test_approved_renewal_cannot_be_detached_from_its_settled_fee(self):
        settle_extension_fee(self.term)
        renewal=self.renewal()
        renewal.renewal_of=None
        renewal.exception_reference='An unrelated date exception does not authorize detaching the fee'
        with self.assertRaises(ValidationError):
            renewal.save()

    def test_cached_receipt_parent_cannot_spend_a_balance_waived_since_it_was_loaded(self):
        import uuid
        from estate_app.estate.charges import prepare_charge_decision
        charge=self.charge()
        pending=self.Receipt(charge=charge,amount=Decimal('900'),payment_date=dt.date(2026,11,2),
                             receipt_reference='Receipt prepared before waiver')
        fresh=self.Charge.objects.get(pk=charge.pk)
        boss=User.objects.create_superuser('cached-waiver-reviewer',password='test')
        prepare_charge_decision(fresh,{'action':'waiver','waiver_amount':Decimal('200'),
            'reference':'Approved appeal','reason':'Recorded after receipt preparation'},boss,uuid.uuid4())
        fresh.save()
        with self.assertRaises(ValidationError):
            pending.save()
        self.assertEqual(charge.payments.count(),0)


class EstateChargeApiTests(TestCase):
    def setUp(self):
        self.enterContext(patch('django.utils.timezone.localdate',return_value=dt.date(2026,11,13)))
        self.term=charge_term()
        self.charge=assessed_charge(self.term)
        self.staff=User.objects.create_user('charge-entry-staff')
        self.boss=User.objects.create_superuser('charge-decision-reviewer',password='test')
        self.api=APIClient()
        self.api.force_authenticate(self.staff)
        self.Receipt=apps.get_model('estate_app','EstateChargePayment')

    def payment(self,amount='400'):
        return self.Receipt.objects.create(charge=self.charge,amount=Decimal(amount),
            payment_date=dt.date(2026,11,2),receipt_reference='Synthetic retained receipt')

    def decision(self,**changes):
        return {**dict(action='waiver',waiver_amount='200.00',reference='Approved appeal REF-1',
                       reason='Reviewed appeal against the assessed incident'),**changes}

    def test_staff_api_requires_explicit_tax_and_owns_receipt_actor(self):
        url='/api/estate-charges/'
        payload={'allotment':self.term.pk,'kind':'damage_recovery','description':'Approved damage assessment',
            'assessed_on':'2026-11-01','authority_reference':'Damage decision REF-2',
            'net_amount':'500','due_date':'2026-11-10'}
        self.assertEqual(self.api.post(url,payload,format='json').status_code,400)
        response=self.api.post(url,{**payload,'tax_amount':'0.00'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['gross_amount'],'500.00')
        self.assertEqual(response.data['created_by'],self.staff.pk)
        response=self.api.post('/api/estate-charge-payments/',{'charge':self.charge.pk,'amount':'400',
            'payment_date':'2026-11-02','receipt_reference':'Actual synthetic receipt','recorded_by':self.boss.pk},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['recorded_by'],self.staff.pk)
        self.assertEqual(response.data['source'],'receipt')
        detail=self.api.get(f'/api/estate-charges/{self.charge.pk}/').data
        self.assertEqual(detail['balance_due'],'600.00')
        self.assertEqual(detail['shop_code'],'CHARGE-101')

    def test_waiver_preview_is_read_only_bound_and_idempotent(self):
        from estate_app.models import ActivityEntry
        self.payment()
        url=f'/api/estate-charges/{self.charge.pk}/'
        self.assertEqual(self.api.post(url+'decision-preview/',self.decision(),format='json').status_code,403)
        self.api.force_authenticate(self.boss)
        count=ActivityEntry.objects.count()
        preview=self.api.post(url+'decision-preview/',self.decision(),format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        self.assertEqual(preview.data['after']['balance_due'],'400.00')
        self.assertEqual(ActivityEntry.objects.count(),count)
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.waiver_amount,0)
        confirmed=self.api.post(url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(confirmed.status_code,200,confirmed.data)
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.waiver_amount,Decimal('200'))
        self.assertEqual(self.charge.waived_by_id,self.boss.pk)
        self.assertEqual(self.charge.net_amount,Decimal('1000'))
        self.assertEqual(self.charge.payments.count(),1)
        count=ActivityEntry.objects.count()
        again=self.api.post(url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(again.status_code,200,again.data)
        self.assertTrue(again.data['already_applied'])
        self.assertEqual(ActivityEntry.objects.count(),count)

    def test_stale_or_excess_waivers_cannot_reduce_the_balance(self):
        self.payment()
        self.api.force_authenticate(self.boss)
        url=f'/api/estate-charges/{self.charge.pk}/'
        self.assertEqual(self.api.post(url+'decision-preview/',self.decision(waiver_amount='700'),format='json').status_code,400)
        preview=self.api.post(url+'decision-preview/',self.decision(),format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        self.payment('100')
        confirmed=self.api.post(url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(confirmed.status_code,400,confirmed.data)
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.waiver_amount,0)
        self.assertEqual(self.charge.amount_paid,Decimal('500'))

    def test_assessment_correction_uses_reviewed_action_not_ordinary_patch(self):
        self.payment()
        url=f'/api/estate-charges/{self.charge.pk}/'
        self.api.force_authenticate(self.boss)
        response=self.api.patch(url,{'net_amount':'1200','change_reason':'Attempt ordinary reduction'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        decision={'action':'assessment','net_amount':'1200','tax_amount':'0',
                  'reference':'Corrected assessment REF-2','reason':'Correct amount from the deciding order'}
        preview=self.api.post(url+'decision-preview/',decision,format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        self.assertEqual(preview.data['after']['balance_due'],'800.00')
        confirmed=self.api.post(url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(confirmed.status_code,200,confirmed.data)
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.net_amount,Decimal('1200'))
        self.assertEqual(self.charge.authority_reference,'Corrected assessment REF-2')
        self.assertEqual(self.charge.amount_paid,Decimal('400'))

    def test_assessments_and_security_sources_cannot_be_forged_or_erased(self):
        url=f'/api/estate-charges/{self.charge.pk}/'
        self.assertEqual(self.api.patch(url,{'waiver_amount':'1000','change_reason':'Attempt direct waiver'},format='json').status_code,400)
        self.assertEqual(self.api.get(url+'deletion-preview/').status_code,400)
        self.assertEqual(self.api.post('/api/estate-charge-payments/',{'charge':self.charge.pk,'amount':'100',
            'payment_date':'2026-11-02','receipt_reference':'Unpaired operation','source':'security_application'},format='json').status_code,400)

    def test_financial_confirmation_rejects_other_reviewers_expiry_and_bad_input(self):
        import time
        url=f'/api/estate-charges/{self.charge.pk}/'
        self.api.force_authenticate(self.boss)
        preview=self.api.post(url+'decision-preview/',self.decision(),format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        other=User.objects.create_superuser('other-charge-reviewer',password='test')
        self.api.force_authenticate(other)
        self.assertEqual(self.api.post(url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json').status_code,403)
        self.api.force_authenticate(self.boss)
        for body in ([],{'confirmation':'invalid-signature'}):
            self.assertEqual(self.api.post(url+'apply-decision/',body,format='json').status_code,400)
        later=time.time()+601
        with patch('django.core.signing.time.time',return_value=later):
            self.assertEqual(self.api.post(url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json').status_code,400)
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.waiver_amount,0)

    def test_dashboard_and_attention_include_each_charge_once(self):
        self.payment()
        stats=self.api.get('/api/dashboard/').data
        self.assertEqual(stats['total_billed'],1000)
        self.assertEqual(stats['total_collected'],400)
        self.assertEqual(stats['total_outstanding'],600)
        self.assertEqual(stats['charge_summary']['outstanding'],'600.00')
        attention=self.api.get('/api/estate/attention/?kind=charge_due').data['results']
        self.assertEqual(len(attention),1)
        self.assertEqual(attention[0]['charge'],self.charge.pk)
        self.assertEqual(attention[0]['allotment'],self.term.pk)
        self.payment('600')
        self.assertEqual(self.api.get('/api/estate/attention/?kind=charge_due').data['results'],[])

    def test_allotment_exposes_renewal_fee_readiness_without_inventing_receipts(self):
        url=f'/api/allotments/{self.term.pk}/'
        self.assertFalse(self.api.get(url).data['renewal_fee_settled'])
        fee=settle_extension_fee(self.term)
        response=self.api.get(url).data
        self.assertTrue(response['renewal_fee_settled'])
        self.assertEqual(response['renewal_fee_charge_id'],fee.pk)

    def test_admin_registers_charge_workflows_and_keeps_decisions_read_only(self):
        from django.contrib import admin
        from types import SimpleNamespace
        self.client.force_login(self.boss)
        response=self.client.get(f'/admin/estate_app/estatecharge/{self.charge.pk}/change/')
        self.assertEqual(response.status_code,200)
        registered=admin.site._registry[self.charge.__class__]
        request=SimpleNamespace(user=self.boss)
        self.assertFalse(registered.has_delete_permission(request,self.charge))
        self.assertIn('net_amount',registered.get_readonly_fields(request,self.charge))


class EstateChargeConcurrencyTests(ActivityTransactionTestCase):
    def test_concurrent_receipts_cannot_both_spend_the_same_remaining_balance(self):
        import threading
        from django.db import OperationalError,close_old_connections
        self.assertIn('estatecharge',apps.all_models['estate_app'],'One-off estate charges are not implemented yet')
        Charge=apps.get_model('estate_app','EstateCharge')
        Receipt=apps.get_model('estate_app','EstateChargePayment')
        term=charge_term()
        charge=Charge.objects.create(allotment=term,kind='incident_fine',description='Concurrent synthetic incident',
            assessed_on=dt.date(2026,1,1),authority_reference='Approved synthetic incident',
            net_amount=Decimal('1000'),tax_amount=Decimal('0'),due_date=dt.date(2026,1,10))
        ready=threading.Barrier(2)
        outcomes=[]
        def pay():
            close_old_connections()
            try:
                ready.wait(timeout=5)
                Receipt.objects.create(charge_id=charge.pk,amount=Decimal('600'),
                    payment_date=dt.date(2026,1,2),receipt_reference='Concurrent synthetic receipt')
                outcomes.append('recorded')
            except (ValidationError,OperationalError):
                outcomes.append('conflict')
            finally:
                close_old_connections()
        threads=[threading.Thread(target=pay) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes,['recorded','conflict'])
        self.assertEqual(charge.amount_paid,Decimal('600'))
