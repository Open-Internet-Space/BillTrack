import datetime as dt
from decimal import Decimal
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from estate_app.tests.test_estate_charges import charge_term, settle_extension_fee
from estate_app.tests.transaction_case import ActivityTransactionTestCase


class SecurityDomainTests(TestCase):
    def setUp(self):
        self.enterContext(patch('django.utils.timezone.localdate',return_value=dt.date(2026,11,13)))
        self.term=charge_term()
        self.actor=User.objects.create_superuser('security-reviewer',password='test')

    def test_required_deposit_uses_three_initial_rents_and_ceiling_hundred(self):
        from estate_app.estate.security import required_security
        self.assertEqual(required_security('1800'),Decimal('5400'))
        self.assertEqual(required_security(Decimal('5401')/3),Decimal('5500'))
        self.assertEqual(required_security('1800.34'),Decimal('5500'))
        self.assertEqual(required_security('0.01'),Decimal('100'))
        with self.assertRaises(ValidationError):
            required_security('0')

    def test_requirement_records_original_deadline_and_calendar_month_refund_review(self):
        self.term.security_initial_rent=Decimal('1800')
        self.term.security_required_amount=Decimal('5400')
        self.term.security_requirement_reference='Approved initial security basis'
        self.term.security_requirement_reason='Actual accepted monthly rent at initial award'
        self.term._security_actor=self.actor
        self.term._security_reason='Approved initial requirement'
        self.term.save()
        self.term.refresh_from_db()
        self.assertEqual(self.term.security_due_date,dt.date(2026,1,8))
        self.assertEqual(self.term.security_refund_review_due,dt.date(2027,3,31))
        self.term.end_date=dt.date(2026,11,30)
        self.assertEqual(self.term.security_refund_review_due,dt.date(2027,2,28))
        self.term.security_extended_due_date=dt.date(2026,1,20)
        with self.assertRaises(ValidationError):
            self.term.save()
        self.term.security_extension_reference='Approved extension of deposit deadline'
        self.term.save()
        self.assertEqual(self.term.security_effective_due_date,dt.date(2026,1,20))

    def test_movement_balance_is_a_separate_liability_and_cannot_go_negative(self):
        self.assertIn('securitymovement',apps.all_models['estate_app'])
        Movement=apps.get_model('estate_app','SecurityMovement')
        Movement.objects.create(original_award=self.term,kind='received',amount=Decimal('5400'),
            effective_date=dt.date(2026,1,2),reference='Actual synthetic DD reference',reason='Security deposit received',recorded_by=self.actor)
        self.assertEqual(self.term.security_held,Decimal('5400'))
        debit=Movement(original_award=self.term,kind='refunded',amount=Decimal('5500'),
            effective_date=dt.date(2026,11,13),reference='Synthetic refund approval',reason='Reviewed clearance',recorded_by=self.actor)
        debit._security_authorized=True
        with self.assertRaises(ValidationError):
            debit.save()
        debit.amount=Decimal('400')
        debit.save()
        self.assertEqual(self.term.security_held,Decimal('5000'))
        received=Movement.objects.get(kind='received')
        received.amount=Decimal('10000')
        with self.assertRaises(ValidationError):
            received.save()
        with self.assertRaises(ValidationError):
            received.delete()

    def test_ordinary_requirement_and_unreviewed_debit_are_rejected(self):
        self.assertIn('security_required_amount',{field.name for field in self.term._meta.fields})
        self.term.security_initial_rent=Decimal('1800')
        self.term.security_required_amount=Decimal('5400')
        self.term.security_requirement_reference='Approval'
        self.term.security_requirement_reason='Approved initial rent'
        with self.assertRaises(ValidationError):
            self.term.save()
        Movement=apps.get_model('estate_app','SecurityMovement')
        with self.assertRaises(ValidationError):
            Movement.objects.create(original_award=self.term,kind='forfeited',amount=Decimal('100'),
                effective_date=dt.date(2026,11,13),reference='Decision',reason='Not a reviewed operation',recorded_by=self.actor)

    def test_bill_security_settlement_requires_a_matching_movement_and_is_protected(self):
        import uuid
        from estate_app.models import Bill, Payment
        self.assertIn('source',{field.name for field in Payment._meta.fields})
        Movement=apps.get_model('estate_app','SecurityMovement')
        bill=Bill.objects.create(tenant=self.term.tenant,allotment=self.term,billing_category='allotment',
            month=11,year=2026,rent=1000,electric=0,water=0)
        operation_id=uuid.uuid4()
        payment=Payment(bill=bill,amount=Decimal('400'),payment_date=dt.date(2026,11,13),
            source='security_application',operation_id=operation_id,recorded_by=self.actor)
        with self.assertRaises(ValidationError):
            payment.save()
        Movement.objects.create(original_award=self.term,kind='received',amount=Decimal('1000'),
            effective_date=dt.date(2026,1,2),reference='Synthetic DD',reason='Security received',recorded_by=self.actor)
        movement=Movement(original_award=self.term,kind='applied',amount=Decimal('400'),
            effective_date=dt.date(2026,11,13),reference='Approved application',reason='Apply to reviewed bill balance',
            recorded_by=self.actor,operation_id=operation_id,applied_bill=bill)
        movement._security_authorized=True
        movement.save()
        payment._security_authorized=True
        payment.save()
        bill.refresh_from_db()
        self.assertEqual(bill.amount_paid,Decimal('400'))
        self.assertEqual(self.term.security_held,Decimal('600'))
        payment.amount=Decimal('500')
        with self.assertRaises(ValidationError):
            payment.save()
        with self.assertRaises(ValidationError):
            Payment.objects.filter(pk=payment.pk).update(source='receipt',operation_id=None)
        with self.assertRaises(ValidationError):
            Payment.objects.filter(pk=payment.pk).delete()

    def test_backdated_debit_cannot_make_an_intermediate_held_balance_negative(self):
        Movement=apps.get_model('estate_app','SecurityMovement')
        base=dict(original_award=self.term,reference='Synthetic authority',reason='Reviewed synthetic movement',recorded_by=self.actor)
        Movement.objects.create(**base,kind='received',amount=100,effective_date=dt.date(2026,1,2))
        refund=Movement(**base,kind='refunded',amount=100,effective_date=dt.date(2026,1,10))
        refund._security_authorized=True
        refund.save()
        Movement.objects.create(**base,kind='received',amount=100,effective_date=dt.date(2026,1,20))
        backdated=Movement(**base,kind='refunded',amount=100,effective_date=dt.date(2026,1,5))
        backdated._security_authorized=True
        with self.assertRaises(ValidationError):
            backdated.save()
        self.assertEqual(self.term.security_held,100)

    def test_charge_application_keeps_pair_identity_and_cannot_cross_shops_for_the_same_person(self):
        import uuid
        from estate_app.models import Allotment, EstateChargePayment, Shop
        from estate_app.tests.test_estate_charges import assessed_charge
        Movement=apps.get_model('estate_app','SecurityMovement')
        charge=assessed_charge(self.term)
        base=dict(original_award=self.term,reference='Synthetic approval',reason='Approved deposit operation',recorded_by=self.actor)
        Movement.objects.create(**base,kind='received',amount=1000,effective_date=dt.date(2026,1,2))
        operation_id=uuid.uuid4()
        applied=Movement(**base,kind='applied',amount=400,effective_date=dt.date(2026,11,13),
                         applied_charge=charge,operation_id=operation_id)
        applied._security_authorized=True
        applied.save()
        receipt=EstateChargePayment(charge=charge,amount=Decimal('400'),payment_date=dt.date(2026,11,13),
            receipt_reference='Approved deposit application',source='security_application',operation_id=operation_id,recorded_by=self.actor)
        receipt._security_authorized=True
        receipt.save()
        self.assertEqual(charge.balance_due,600)
        receipt.source='receipt'
        with self.assertRaises(ValidationError):
            receipt.delete()
        with self.assertRaises(ValidationError):
            EstateChargePayment.objects.filter(pk=receipt.pk).delete()
        other=Allotment.objects.create(shop=Shop.objects.create(code='OTHER-DEPOSIT',name='Other shop',category='utility'),tenant=self.term.tenant,
            source_notice='368/2025',award_reference='Other award',letter_issued_on=dt.date(2026,1,1),
            start_date=dt.date(2026,1,1),end_date=dt.date(2026,12,31),actual_area=100,measurement_reference='Other measured area')
        wrong=assessed_charge(other)
        cross=Movement(**base,kind='applied',amount=100,effective_date=dt.date(2026,11,13),
                       applied_charge=wrong,operation_id=uuid.uuid4())
        cross._security_authorized=True
        with self.assertRaises(ValidationError):
            cross.save()
        self.assertEqual(self.term.security_held,600)


class SecurityApiTests(TestCase):
    def setUp(self):
        self.enterContext(patch('django.utils.timezone.localdate',return_value=dt.date(2026,11,13)))
        self.term=charge_term()
        self.staff=User.objects.create_user('security-receipt-staff')
        self.boss=User.objects.create_superuser('security-action-reviewer',password='test')
        self.api=APIClient()
        self.api.force_authenticate(self.boss)
        self.url=f'/api/estate-security/{self.term.pk}/'

    def requirement(self):
        return dict(action='requirement',initial_monthly_rent='1800.34',reference='Approved initial deposit',
                    reason='Reviewed actual initial monthly rent')

    def confirm(self,data):
        preview=self.api.post(self.url+'decision-preview/',data,format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        result=self.api.post(self.url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(result.status_code,200,result.data)
        return preview,result

    def receive(self,amount='1000'):
        self.api.force_authenticate(self.staff)
        result=self.api.post('/api/security-movements/',dict(original_award=self.term.pk,amount=amount,
            effective_date='2026-11-01',reference='Actual synthetic DD-1',reason='Actual deposit receipt',recorded_by=self.boss.pk),format='json')
        self.assertEqual(result.status_code,201,getattr(result,'data',result.content))
        self.assertEqual(result.data['recorded_by'],self.staff.pk)
        self.api.force_authenticate(self.boss)
        return result

    def test_carry_forward_records_renewal_choice_without_a_second_receipt(self):
        from estate_app.models import ActivityEntry, SecurityMovement

        settle_extension_fee(self.term)
        payload = dict(tenant=self.term.tenant_id, renewal_of=self.term.pk,
            award_reference='Reviewed extension', letter_issued_on='2026-11-13', start_date='2027-01-01',
            end_date='2027-12-31', actual_area='150', measurement_reference='Original measurement',
            approval_reference='Renewal approval', performance_reference='Performance review', carry_forward_deposit=True)
        rejected = self.api.post('/api/allotments/', payload, format='json')
        self.assertEqual(rejected.status_code, 400, rejected.data)
        self.assertIn('carry_forward_deposit', rejected.data)
        self.receive('5500')
        renewed = self.api.post('/api/allotments/', {**payload, 'carry_forward_deposit': False}, format='json')
        self.assertEqual(renewed.status_code, 201, renewed.data)
        saved = self.api.patch(f"/api/allotments/{renewed.data['id']}/",
            {'carry_forward_deposit': True, 'change_reason': 'Allottee chose to retain the deposit'}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertIs(saved.data['carry_forward_deposit'], True)
        self.assertEqual(saved.data['original_award_id'], self.term.pk)
        self.assertEqual(SecurityMovement.objects.count(), 1)
        self.assertEqual(self.api.get(self.url).data['held'], '5500.00')
        audit = ActivityEntry.objects.filter(record_type='estate_app.allotment', record_id=renewed.data['id'], action='update').latest('id')
        self.assertTrue(audit.after['carry_forward_deposit'])

    def test_handover_clearance_respects_the_admin_switch(self):
        from estate_app.models import SystemSettings

        message = 'Physical handover of the final term is not confirmed.'
        self.assertNotIn(message, self.api.get(self.url).data['clearance_issues'])
        settings, _ = SystemSettings.objects.get_or_create(pk=1)
        settings.allotment_details_enabled = True
        settings.save(update_fields=['allotment_details_enabled'])
        issues = self.api.get(self.url).data['clearance_issues']
        self.assertIn(message, issues)
        self.assertIn('The final approved term has not ended.', issues)

    def test_receipt_can_precede_the_original_letter_and_survive_review_and_export(self):
        from estate_app.data_transfer.serialization import export_data, validate_data

        receipt = self.api.post('/api/security-movements/', dict(original_award=self.term.pk, amount='5500',
            effective_date='2025-12-26', reference='Synthetic advance voucher', reason='Documented advance deposit'), format='json')
        self.assertEqual(receipt.status_code, 201, receipt.data)
        _, result = self.confirm(self.requirement())
        self.assertEqual(result.data['account']['held'], '5500.00')
        self.assertEqual(result.data['account']['outstanding_requirement'], '0.00')
        validate_data(export_data())

    def test_deposit_timing_uses_offer_deadline_or_order_date_and_preserves_legacy_terms(self):
        from estate_app.data_transfer.serialization import export_data, validate_data

        _, legacy = self.confirm(self.requirement())
        self.assertEqual((legacy.data['account']['timing'], legacy.data['account']['due_date']), ('', '2026-01-08'))
        before = {**self.requirement(), 'timing': 'before', 'offer_date': '2025-12-15'}
        bad = self.api.post(self.url+'decision-preview/', {**before, 'pre_order_due_date': '2026-01-02'}, format='json')
        self.assertEqual(bad.status_code, 400)
        _, saved = self.confirm({**before, 'pre_order_due_date': '2025-12-28'})
        account = saved.data['account']
        self.assertEqual((account['timing'], account['offer_date'], account['due_date']), ('before', '2025-12-15', '2025-12-28'))
        validate_data(export_data())
        _, cutoff = self.confirm({**before, 'pre_order_due_date': None})
        self.assertEqual(cutoff.data['account']['due_date'], '2026-01-01')
        _, after = self.confirm({**self.requirement(), 'timing': 'after'})
        account = after.data['account']
        self.assertEqual((account['timing'], account['offer_date'], account['due_date']), ('after', None, '2026-01-08'))

    def test_requirement_preview_has_no_writes_and_confirmation_is_bound_and_idempotent(self):
        from estate_app.models import ActivityEntry
        count=ActivityEntry.objects.count()
        preview=self.api.post(self.url+'decision-preview/',self.requirement(),format='json')
        self.assertEqual(preview.status_code,200,getattr(preview,'data',preview.content))
        self.assertEqual(ActivityEntry.objects.count(),count)
        self.term.refresh_from_db()
        self.assertIsNone(self.term.security_required_amount)
        self.assertEqual(preview.data['after']['required_amount'],'5500.00')
        payload={'confirmation':preview.data['confirmation']}
        self.api.force_authenticate(self.staff)
        self.assertEqual(self.api.post(self.url+'apply-decision/',payload,format='json').status_code,403)
        self.api.force_authenticate(self.boss)
        result=self.api.post(self.url+'apply-decision/',payload,format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['account']['due_date'],'2026-01-08')
        count=ActivityEntry.objects.count()
        replay=self.api.post(self.url+'apply-decision/',payload,format='json')
        self.assertTrue(replay.data['already_applied'])
        self.assertEqual(ActivityEntry.objects.count(),count)

    def test_charge_application_creates_one_pair_and_rejects_a_stale_preview(self):
        from estate_app.models import EstateChargePayment,SecurityMovement
        from estate_app.tests.test_estate_charges import assessed_charge
        charge=assessed_charge(self.term)
        self.receive()
        data=dict(action='apply_charge',charge=charge.pk,amount='400',effective_date='2026-11-13',
                  reference='Reviewed security application',reason='Settle part of assessed fine')
        preview,result=self.confirm(data)
        self.assertEqual(result.data['account']['held'],'600.00')
        movement=SecurityMovement.objects.get(kind='applied')
        receipt=EstateChargePayment.objects.get(source='security_application')
        self.assertEqual(movement.operation_id,receipt.operation_id)
        replay=self.api.post(self.url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertTrue(replay.data['already_applied'])
        self.assertEqual(SecurityMovement.objects.filter(kind='applied').count(),1)
        stale=self.api.post(self.url+'decision-preview/',data,format='json')
        self.assertEqual(stale.status_code,200,stale.data)
        EstateChargePayment.objects.create(charge=charge,amount=100,payment_date=dt.date(2026,11,13),receipt_reference='New actual receipt')
        rejected=self.api.post(self.url+'apply-decision/',{'confirmation':stale.data['confirmation']},format='json')
        self.assertEqual(rejected.status_code,400,rejected.data)
        self.assertEqual(self.term.security_held,600)

    def test_refund_requires_clearance_or_an_explicit_exception_and_retains_history(self):
        from estate_app.models import SecurityMovement
        self.confirm(self.requirement())
        self.receive()
        data=dict(action='refund',amount='200',effective_date='2026-11-13',reference='Actual authorized refund REF-1',
                  reason='Reviewed refund request with actual evidence')
        blocked=self.api.post(self.url+'decision-preview/',data,format='json')
        self.assertEqual(blocked.status_code,400,blocked.data)
        data['exception_reference']='Explicit authority for refund before handover/clearance'
        _,result=self.confirm(data)
        self.assertEqual(result.data['account']['held'],'800.00')
        self.term.refresh_from_db()
        self.assertEqual(self.term.refund_review_status,'exception')
        self.assertIn(data['exception_reference'],self.term.refund_review_reference)
        self.assertEqual(SecurityMovement.objects.filter(kind='refunded').count(),1)

    def test_pair_failure_rolls_back_the_movement_and_its_audit(self):
        from estate_app.models import Bill,Payment,SecurityMovement,ActivityEntry
        bill=Bill.objects.create(tenant=self.term.tenant,allotment=self.term,billing_category='allotment',month=11,year=2026,rent=1000,electric=0,water=0)
        self.receive()
        data=dict(action='apply_bill',bill=bill.pk,amount='400',effective_date='2026-11-13',
                  reference='Reviewed bill application',reason='Atomic settlement test')
        preview=self.api.post(self.url+'decision-preview/',data,format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        count=ActivityEntry.objects.count()
        with patch.object(Payment,'save',side_effect=ValidationError('Synthetic failure after movement insert')):
            result=self.api.post(self.url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(result.status_code,400,result.data)
        self.assertEqual(SecurityMovement.objects.filter(kind='applied').count(),0)
        self.assertEqual(ActivityEntry.objects.count(),count)
        self.assertEqual(self.term.security_held,1000)

    def test_normal_refund_requires_actual_handover_clear_documents_and_no_person_dues(self):
        self.confirm(self.requirement())
        self.receive('5500')
        self.term.refresh_from_db()
        shop=self.term.shop
        shop.availability_confirmed_on=dt.date(2026,1,1)
        shop.availability_reference='Synthetic initial availability evidence'
        shop.save()
        self.term.end_date=dt.date(2026,10,31)
        self.term.possession_date=dt.date(2026,1,1)
        self.term.possession_reference='Synthetic possession record'
        self.term.handover_date=dt.date(2026,11,1)
        self.term.handover_reference='Synthetic final handover record'
        self.term.save()
        for item in self.term.requirements.all():
            item.applicable=False
            item.not_applicable_reason='Explicit synthetic clearance fixture'
            item.save()
        _,result=self.confirm(dict(action='refund',amount='5500',effective_date='2026-11-13',
            reference='Actual full refund reference',reason='Reviewed final clearance and refund'))
        self.assertEqual(result.data['account']['held'],'0.00')
        self.assertEqual(result.data['account']['refund_review_status'],'cleared')

    def test_forged_receipt_and_expired_or_malformed_confirmation_are_rejected(self):
        import time
        from estate_app.models import SecurityMovement
        self.api.force_authenticate(self.staff)
        response=self.api.post('/api/security-movements/',dict(original_award=self.term.pk,kind='refunded',
            amount='100',effective_date='2026-11-13',reference='Forged debit',reason='No review'),format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(SecurityMovement.objects.count(),0)
        self.api.force_authenticate(self.boss)
        preview=self.api.post(self.url+'decision-preview/',self.requirement(),format='json')
        for payload in [{'confirmation':[]},{'confirmation':'invalid-signature'}]:
            self.assertEqual(self.api.post(self.url+'apply-decision/',payload,format='json').status_code,400)
        with patch('django.core.signing.time.time',return_value=time.time()+601):
            response=self.api.post(self.url+'apply-decision/',{'confirmation':preview.data['confirmation']},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.term.refresh_from_db()
        self.assertIsNone(self.term.security_required_amount)

    def test_admin_can_record_a_receipt_but_not_edit_or_delete_movement_history(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from estate_app.models import SecurityMovement
        request=RequestFactory().get('/')
        request.user=self.boss
        registered=admin.site._registry[SecurityMovement]
        form_class=registered.get_form(request)
        form=form_class(data={'original_award':self.term.pk,'amount':'1000','effective_date':'2026-11-01',
                             'reference':'Actual synthetic DD admin','reason':'Actual security receipt evidence'})
        self.assertTrue(form.is_valid(),form.errors)
        obj=form.save(commit=False)
        registered.save_model(request,obj,form,False)
        self.assertEqual(obj.recorded_by,self.boss)
        self.assertEqual(obj.kind,'received')
        self.assertFalse(registered.has_change_permission(request,obj))
        self.assertFalse(registered.has_delete_permission(request,obj))

    def test_dashboard_counts_security_receipts_and_applications_separately_from_cash_collection(self):
        from estate_app.tests.test_estate_charges import assessed_charge
        charge=assessed_charge(self.term)
        self.receive()
        self.confirm(dict(action='apply_charge',charge=charge.pk,amount='400',effective_date='2026-11-13',
                          reference='Approved charge application',reason='Settle fine from held deposit'))
        stats=self.api.get('/api/dashboard/').data
        self.assertEqual(stats['total_collected'],0)
        self.assertEqual(stats['total_settled'],400)
        self.assertEqual(stats['total_outstanding'],600)
        self.assertEqual(stats['charge_summary']['paid'],'0.00')
        self.assertEqual(stats['charge_summary']['applied'],'400.00')
        self.assertEqual(stats['security_summary']['received'],'1000.00')
        self.assertEqual(stats['security_summary']['held'],'600.00')
        self.confirm(dict(action='forfeit',amount='100',effective_date='2026-11-13',
                          reference='Approved forfeiture',reason='Separate liability decision, not fine settlement'))
        self.assertEqual(self.api.get('/api/dashboard/').data['total_outstanding'],600)

    def test_attention_tracks_actual_deposit_shortfall_and_refund_review_date(self):
        self.confirm(self.requirement())
        rows=self.api.get('/api/estate/attention/?kind=deposit_due').data['results']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['shortfall'],'5500.00')
        self.receive('5500')
        self.assertEqual(self.api.get('/api/estate/attention/?kind=deposit_due').data['results'],[])
        self.term.refresh_from_db()
        self.term.end_date=dt.date(2026,4,30)
        self.term.save()
        rows=self.api.get('/api/estate/attention/?kind=refund_review').data['results']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['due_date'],'2026-07-30')
        self.assertEqual(rows[0]['security'],self.term.pk)

    def test_backdated_bill_application_cannot_pay_interest_that_had_not_accrued(self):
        from estate_app.models import Bill,RentRevision
        self.term.tenant.gst_applicable=False
        self.term.tenant.save()
        RentRevision.objects.create(original_award=self.term,effective_date=dt.date(2026,4,1),rate=20,
            approval_reference='Accepted rate already revised as of April',reason='Actual reviewed basis')
        bill=Bill.objects.create(tenant=self.term.tenant,allotment=self.term,billing_category='allotment',
            billing_policy='notices_368_369',month=11,year=2026,full_month_rent=3000,rent=3000,
            electric=0,water=0,raised_date=dt.date(2026,11,1),
            email_dispatched_at=dt.datetime(2026,11,1,10,tzinfo=dt.timezone.utc),
            dispatch_recipient='synthetic@example.invalid',dispatch_message_reference='Actual synthetic transmission',dispatch_sender=self.boss)
        self.receive('5500')
        self.assertGreater(bill.penalty,0)
        data=dict(action='apply_bill',bill=bill.pk,
            amount=str(Decimal('3000')+bill.penalty),interest_amount=str(bill.penalty),effective_date='2026-11-01',
            reference='Backdated reviewed application',reason='Cannot debit held money for future interest')
        response=self.api.post(self.url+'decision-preview/',data,format='json')
        self.assertEqual(response.status_code,400,response.data)
        data['effective_date']='2026-11-13'
        _,result=self.confirm(data)
        bill.refresh_from_db()
        self.assertEqual(bill.status,'Paid')
        self.assertEqual(result.data['account']['held'],'2495.07')

    def test_cash_report_excludes_security_and_statement_reconciles_both_sources(self):
        from estate_app.models import Bill,Payment
        bill=Bill.objects.create(tenant=self.term.tenant,allotment=self.term,billing_category='allotment',
            month=11,year=2026,rent=1000,electric=0,water=0)
        self.receive()
        self.confirm(dict(action='apply_bill',bill=bill.pk,amount='400',effective_date='2026-11-13',
            reference='Approved security application',reason='Separate settlement from cash collection'))
        Payment.objects.create(bill=bill,amount=100,payment_date=dt.date(2026,11,12),receipt_no='Actual cash receipt')
        cash=self.api.get('/api/reports/',{'report':'payments','from':'2026-11-01','to':'2026-11-13'}).data
        self.assertEqual(cash['count'],1)
        self.assertEqual(cash['totals']['received'],'100.00')
        statement=self.api.get('/api/reports/',{'report':'statement','from':'2026-11-01','to':'2026-11-13'}).data
        self.assertEqual(statement['totals']['paid'],'500.00')
        self.assertEqual(statement['totals']['received'],'100.00')
        self.assertEqual(statement['totals']['security_applied'],'400.00')
        self.assertEqual(Decimal(statement['totals']['closing']),bill.total_amount-500)


class SecurityConcurrencyTests(ActivityTransactionTestCase):
    def test_concurrent_confirmations_cannot_apply_the_same_held_money_twice(self):
        import threading
        from django.db import close_old_connections
        from estate_app.models import EstateChargePayment,SecurityMovement
        from estate_app.tests.test_estate_charges import assessed_charge
        with patch('django.utils.timezone.localdate',return_value=dt.date(2026,11,13)):
            term=charge_term()
            boss=User.objects.create_superuser('concurrent-security-reviewer',password='test')
            charge=assessed_charge(term)
            SecurityMovement.objects.create(original_award=term,kind='received',amount=1000,
                effective_date=dt.date(2026,11,1),reference='Synthetic DD',reason='Actual synthetic receipt',recorded_by=boss)
            api=APIClient();api.force_authenticate(boss)
            url=f'/api/estate-security/{term.pk}/'
            data=dict(action='apply_charge',charge=charge.pk,amount='600',effective_date='2026-11-13',
                      reference='Reviewed concurrent application',reason='Do not spend held money twice')
            tokens=[]
            for _ in range(2):
                preview=api.post(url+'decision-preview/',data,format='json')
                self.assertEqual(preview.status_code,200,preview.data)
                tokens.append(preview.data['confirmation'])
            ready=threading.Barrier(2);outcomes=[]
            def confirm(token):
                close_old_connections()
                try:
                    client=APIClient();client.force_authenticate(boss)
                    ready.wait(timeout=5)
                    response=client.post(url+'apply-decision/',{'confirmation':token},format='json')
                    outcomes.append(response.status_code)
                finally:
                    close_old_connections()
            threads=[threading.Thread(target=confirm,args=(token,)) for token in tokens]
            for thread in threads:thread.start()
            for thread in threads:thread.join(timeout=15)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(outcomes.count(200),1,outcomes)
            self.assertTrue(all(code in (200,400,409) for code in outcomes),outcomes)
            self.assertEqual(SecurityMovement.objects.filter(kind='applied').count(),1)
            self.assertEqual(EstateChargePayment.objects.filter(source='security_application').count(),1)
            self.assertEqual(term.security_held,400)
            self.assertEqual(charge.balance_due,400)
