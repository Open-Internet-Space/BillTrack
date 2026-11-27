import datetime as dt
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from estate_app.models import Shop, SystemSettings, Tenant


class EstateApiTests(TestCase):
    def setUp(self):
        self.enterContext(patch('django.utils.timezone.localdate', return_value=dt.date(2026, 11, 13)))
        self.user = User.objects.create_superuser('estate-admin', 'estate@example.invalid', 'Synthetic-estate-83!')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.tenant = Tenant.objects.create(name='Estate API allottee', type='Shop')
        self.Allotment = apps.get_model('estate_app', 'Allotment')

    def payload(self, **changes):
        values = dict(tenant=self.tenant.pk, source_notice='368/2025',
                      award_reference='Synthetic award', letter_issued_on='2026-01-01',
                      start_date='2026-01-01', end_date='2026-12-31', actual_area='150',
                      measurement_reference='Measurement memo')
        values.update(changes)
        return values

    def create_term(self, **changes):
        response = self.api.post('/api/allotments/', self.payload(**changes), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.data

    def test_date_exception_saves_approval_and_reason_with_additional_details_off(self):
        from estate_app.data_transfer.serialization import export_data, validate_data

        payload = self.payload(source_notice='', letter_issued_on='2026-01-14',
            exception_reason='The approval covers the earlier start date.')
        rejected = self.api.post('/api/allotments/', payload, format='json')
        self.assertEqual(rejected.status_code, 400)
        payload['exception_reference'] = 'Exception approval No. 7'
        response = self.api.post('/api/allotments/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['exception_reference'], payload['exception_reference'])
        self.assertEqual(response.data['exception_reason'], payload['exception_reason'])
        validate_data(export_data())

    def test_link_misfiled_extension_keeps_bill_rate_and_fee_history(self):
        from estate_app.models import ActivityEntry, Bill, EstateCharge, EstateChargePayment, RentRevision

        original = self.create_term(source_notice='', end_date='2026-06-30', accepted_rate_amount='10')
        later = self.create_term(source_notice='', award_reference='Later award', letter_issued_on='2026-07-01',
            start_date='2026-07-01', end_date='2027-06-30', accepted_rate_amount='10.50')
        later_id = later['id']
        rate = RentRevision.objects.get(original_award_id=later_id)
        bill = Bill.objects.create(tenant=self.tenant, allotment_id=later_id, billing_category='allotment',
            year=2026, month=7, rent=1575)
        fee = EstateCharge.objects.create(allotment_id=later_id, kind='extension_fee', description='Extension into second year',
            assessed_on=dt.date(2026, 7, 1), due_date=dt.date(2026, 7, 8), authority_reference='Circular', net_amount=1000, tax_amount=0)
        receipt = EstateChargePayment.objects.create(charge=fee, amount=100, payment_date=dt.date(2026, 7, 2), receipt_reference='Receipt 1')
        url = f'/api/allotments/{later_id}/'
        payload = dict(previous_id=original['id'], approval='Extension letter', performance='Review minutes', reason='Correct original-award classification', move_fee=True)
        self.assertEqual(self.api.patch(url, {'renewal_of': original['id'], 'change_reason': payload['reason']}, format='json').status_code, 400)
        self.api.force_authenticate(User.objects.create_user('estate-staff'))
        self.assertEqual(self.api.post(url + 'link-extension/', payload, format='json').status_code, 403)
        self.api.force_authenticate(self.user)
        response = self.api.post(url + 'link-extension/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['original_award_id'], original['id'])
        self.assertEqual(response.data['extension_number'], 1)
        for record in (bill, rate, fee, receipt):
            record.refresh_from_db()
        self.assertEqual((bill.allotment_id, bill.rent), (later_id, 1575))
        self.assertEqual(rate.original_award_id, original['id'])
        self.assertEqual((fee.allotment_id, fee.renewal_term_id, fee.balance_due), (original['id'], later_id, 900))
        self.assertEqual(receipt.charge_id, fee.pk)
        self.assertTrue(ActivityEntry.objects.filter(record_type='estate_app.allotment', reason=payload['reason']).exists())
        self.assertEqual(self.api.post(url + 'link-extension/', payload, format='json').status_code, 400)

    def test_delete_term_requires_review_and_preserves_protected_history(self):
        from estate_app.models import ActivityEntry

        term = self.create_term(source_notice='Office award')
        url = f"/api/allotments/{term['id']}/"
        reason = 'Remove an erroneous term'
        self.assertEqual(self.api.delete(url, {'change_reason': reason}, format='json').status_code, 400)
        preview = self.api.get(url + 'deletion-preview/')
        self.assertEqual(preview.status_code, 200, preview.data)
        result = self.api.delete(url, {'change_reason': reason, 'confirmation': preview.data['confirmation']}, format='json')
        self.assertEqual(result.status_code, 204, result.data)
        self.assertTrue(Tenant.objects.filter(pk=self.tenant.pk).exists())
        self.assertTrue(ActivityEntry.objects.filter(record_type='estate_app.allotment', action='delete', reason=reason).exists())

        protected = self.create_term()
        preview = self.api.get(f"/api/allotments/{protected['id']}/deletion-preview/")
        self.assertEqual(preview.status_code, 400, preview.data)
        self.assertTrue(self.Allotment.objects.filter(pk=protected['id']).exists())

    def test_register_terms_need_no_inventory_record(self):
        self.tenant.allotment_description = 'Service counter 12'
        self.tenant.save()
        payload = self.payload(source_notice='Office award')
        response = self.api.post('/api/allotments/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        term = self.Allotment.objects.get(pk=response.data['id'])
        self.assertIsNone(term.shop_id)
        self.assertEqual(response.data['register_label'], self.tenant.display_name)
        self.assertEqual(self.api.get('/api/allotments/', {'search': 'counter 12'}).data['count'], 1)
        self.assertEqual(self.api.post('/api/allotments/', {**payload, 'award_reference': 'Overlap'},
                                      format='json').status_code, 400)
        other = Tenant.objects.create(name=self.tenant.name, allotment_description='Service counter 34', type='Shop')
        sibling = self.api.post('/api/allotments/', {**payload, 'tenant': other.pk}, format='json')
        self.assertEqual(sibling.status_code, 201, sibling.content)
        bill = self.api.post('/api/bills/', {'tenant': self.tenant.pk, 'allotment': term.pk,
            'billing_category': 'allotment', 'month': 6, 'year': 2026, 'full_month_rent': '1100.00'}, format='json')
        self.assertEqual(bill.status_code, 201, bill.content)
        self.assertEqual(self.api.get('/api/shops/').status_code, 404)

    def test_additional_details_default_off_and_generic_rent_can_be_saved_without_references(self):
        from estate_app.data_transfer.serialization import export_data, validate_data

        self.assertFalse(self.api.get('/api/auth/me/').data['allotment_details_enabled'])
        payload = self.payload(accepted_rate_amount='10.00')
        payload.pop('measurement_reference')
        notice = self.api.post('/api/allotments/', payload, format='json')
        self.assertEqual(notice.status_code, 400, notice.content)
        payload.pop('source_notice')
        response = self.api.post('/api/allotments/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        term = self.Allotment.objects.get(pk=response.data['id'])
        self.assertEqual(term.measurement_reference, '')
        self.assertEqual(term.rent_revisions.get().approval_reference, '')
        self.assertEqual(term.rent_revisions.get().effective_date, term.start_date)
        validate_data(export_data())

        settings = SystemSettings.get_settings()
        settings.allotment_details_enabled = True
        settings.save(update_fields=['allotment_details_enabled'])
        self.assertTrue(self.api.get('/api/auth/me/').data['allotment_details_enabled'])
        response = self.api.patch(f'/api/allotments/{term.pk}/', {'possession_date': '2026-01-01',
            'possession_reference': 'Possession memo', 'change_reason': 'Record supporting evidence'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        settings.allotment_details_enabled = False
        settings.save(update_fields=['allotment_details_enabled'])
        response = self.api.patch(f'/api/allotments/{term.pk}/', {'notes': 'Updated note',
            'change_reason': 'Correct note'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['possession_reference'], 'Possession memo')

    def test_premises_feature_can_be_enabled_and_disabled_without_unlinking_terms(self):
        self.assertFalse(self.api.get('/api/auth/me/').data['premises_enabled'])
        self.assertEqual(self.api.get('/api/shops/').status_code, 404)
        settings = SystemSettings.get_settings()
        settings.premises_enabled = True
        settings.save()
        self.assertTrue(self.api.get('/api/auth/me/').data['premises_enabled'])
        response = self.api.post('/api/shops/', {'code': 'COUNTER-1', 'name': 'Service counter',
                                               'category': 'utility'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        premises_id = response.data['id']
        term = self.create_term(shop=premises_id, source_notice='Office award')
        self.assertEqual(term['shop'], premises_id)
        settings.premises_enabled = False
        settings.save()
        self.assertEqual(self.api.get(f'/api/shops/{premises_id}/').status_code, 404)
        url = f"/api/allotments/{term['id']}/"
        self.assertNotIn('shop', self.api.get(url).data)
        self.assertEqual(self.api.patch(url, {'shop': None, 'change_reason': 'Attempt while off'},
                                        format='json').status_code, 400)
        edited = self.api.patch(url, {'notes': 'Terms remain available', 'change_reason': 'Record a note'},
                                format='json')
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(self.Allotment.objects.get(pk=term['id']).shop_id, premises_id)
        self.assertTrue(Shop.objects.filter(pk=premises_id).exists())
        settings.premises_enabled = True
        settings.save()
        self.assertEqual(self.api.get(url).data['shop'], premises_id)

    def test_accepted_area_and_flat_charges_feed_bill_preview_and_save(self):
        for basis, notice, area, amount, expected in [
            ('area', '', '150', '20', '3000.00'),
            ('flat', '', None, '1500.00', '1500.00'),
            ('flat', '368/2025', None, '1800.00', '1800.00'),
        ]:
            with self.subTest(basis=basis, notice=notice):
                entry = Tenant.objects.create(name=f'{basis} {notice}', type='Office')
                term = self.create_term(tenant=entry.pk, source_notice=notice, rent_basis=basis, actual_area=area,
                    measurement_reference='Measured area' if area else '', accepted_rate_amount=amount,
                    approved_rate_reference='Approved award amount', letter_issued_on='2026-10-01',
                    start_date='2026-10-01', end_date='2026-12-31')
                self.assertEqual(term['source_notice'], notice)
                self.assertEqual(term['accepted_rate']['reference'], 'Approved award amount')
                payload = {'tenant': entry.pk, 'allotment': term['id'], 'billing_category': 'allotment',
                    'holiday_start_date': '2026-11-10', 'holiday_end_date': '2026-11-19'}
                if notice:
                    payload['raised_date'] = '2026-11-01'
                preview = self.api.post('/api/bills/preview/', {**payload,
                    'from_year': 2026, 'from_month': 11, 'to_year': 2026, 'to_month': 11}, format='json')
                self.assertEqual(preview.status_code, 200, preview.content)
                self.assertEqual(preview.data['months'][0]['full_month_rent'], expected)
                saved = self.api.post('/api/bills/', {**payload, 'year': 2026, 'month': 11}, format='json')
                self.assertEqual(saved.status_code, 201, saved.content)
                self.assertEqual(saved.data['full_month_rent'], expected)
                self.assertEqual(saved.data['rent'], preview.data['months'][0]['rent'])
                if notice:
                    self.assertIsNone(saved.data['area_snapshot'])
                    self.assertEqual(saved.data['rate_snapshot'], '1800.0000')

    def test_register_and_contract_save_together(self):
        data = self.payload(source_notice='', rent_basis='flat', actual_area=None, measurement_reference='',
            accepted_rate_amount='1500.00', approved_rate_reference='Approved monthly charge')
        rejected = self.api.post('/api/tenants/', {'name': 'Uncommitted record', 'type': 'Office',
            'contract': {**data, 'award_reference': ''}}, format='json')
        self.assertEqual(rejected.status_code, 400, rejected.content)
        self.assertFalse(Tenant.objects.filter(name='Uncommitted record').exists())
        created = self.api.post('/api/tenants/', {'name': 'Integrated allotment', 'type': 'Office',
            'contract': data}, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        entry = Tenant.objects.get(pk=created.data['id'])
        term = entry.allotments.get()
        self.assertEqual(term.tenant_id, entry.pk)
        self.assertEqual(term.rent_revisions.get().rate, 1500)
        url = f'/api/tenants/{entry.pk}/'
        updated = self.api.patch(url, {'allotment_description': 'New description',
            'contract': {'id': term.pk, 'notes': 'Updated contract note'}, 'change_reason': 'Correct details'}, format='json')
        self.assertEqual(updated.status_code, 200, updated.content)
        term.refresh_from_db()
        self.assertEqual(term.notes, 'Updated contract note')
        rejected = self.api.patch(url, {'allotment_description': 'Uncommitted edit',
            'contract': {'id': term.pk, 'end_date': '2020-01-01'}, 'change_reason': 'Invalid date test'}, format='json')
        self.assertEqual(rejected.status_code, 400, rejected.content)
        entry.refresh_from_db()
        self.assertEqual(entry.allotment_description, 'New description')

    def test_ordinary_allottee_rate_history_can_have_multiple_effective_dates(self):
        term = self.create_term(source_notice='', rent_basis='flat', actual_area=None, measurement_reference='',
                                accepted_rate_amount='1000.00')
        for date, amount in [('2026-04-01', '1350.00'), ('2026-05-20', '1425.00')]:
            response = self.api.post('/api/rent-revisions/', {'original_award': term['id'], 'effective_date': date,
                'rate': amount, 'reason': 'Rent recorded for billing'}, format='json')
            self.assertEqual(response.status_code, 201, response.content)
        url = f'/api/rent-revisions/?original_award__tenant={self.tenant.pk}'
        response = self.api.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row['effective_date'] for row in response.data['results']],
                         ['2026-01-01', '2026-04-01', '2026-05-20'])
        preview = self.api.post('/api/bills/preview/', {'tenant': self.tenant.pk, 'allotment': term['id'],
            'from_year': 2026, 'from_month': 3, 'to_year': 2026, 'to_month': 5}, format='json')
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual([row['full_month_rent'] for row in preview.data['months']], ['1000.00', '1350.00', '1425.00'])

    def test_all_missing_contract_is_saved_and_later_activated(self):
        missing = [
            'award_reference', 'letter_issued_on', 'start_date', 'end_date', 'rent_basis',
            'actual_area', 'measurement_reference', 'accepted_rate_amount', 'approved_rate_reference']
        entry = self.api.post('/api/tenants/', {'name': 'Incomplete intake', 'type': 'Office',
            'contract': {'unavailable': missing}}, format='json')
        self.assertEqual(entry.status_code, 201, entry.content)
        tenant = Tenant.objects.get(pk=entry.data['id'])
        self.assertEqual(tenant.contract_draft, {'fields': {}, 'unavailable': sorted(missing)})
        self.assertFalse(tenant.allotments.exists())
        response = self.api.get('/api/estate/attention/', {'kind': 'ending'})
        self.assertFalse(any(item['tenant'] == tenant.pk for item in response.data['results']))
        url = f'/api/tenants/{tenant.pk}/'
        partial = self.api.patch(url, {'contract': {'award_reference': 'Award on file',
            'unavailable': [field for field in missing if field != 'award_reference']},
            'change_reason': 'Record available evidence'}, format='json')
        self.assertEqual(partial.status_code, 200, partial.content)
        self.assertEqual(partial.data['contract_draft']['fields']['award_reference'], 'Award on file')
        details = self.payload(source_notice='', award_reference='Award on file', rent_basis='flat',
            actual_area=None, measurement_reference='', accepted_rate_amount='1500.00',
            approved_rate_reference='Approved charge')
        completed = self.api.patch(url, {'contract': details, 'change_reason': 'Complete known details'}, format='json')
        self.assertEqual(completed.status_code, 200, completed.content)
        tenant.refresh_from_db()
        self.assertEqual(tenant.contract_draft, {})
        self.assertEqual(tenant.allotments.get().award_reference, 'Award on file')

    def test_api_validates_overlap_and_preserves_change_reasons(self):
        term = self.create_term()
        self.assertEqual(term['tenant_name'], self.tenant.name)
        self.assertNotIn('shop', term)
        self.assertEqual(self.api.post('/api/allotments/', self.payload(), format='json').status_code, 400)
        url = f"/api/allotments/{term['id']}/"
        self.assertEqual(self.api.patch(url, {'notes': 'Correction'}, format='json').status_code, 400)
        response = self.api.patch(url, {'notes': 'Correction', 'change_reason': 'Documented correction'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.api.patch(url, {'end_date': '2025-01-01',
            'change_reason': 'Invalid correction'}, format='json').status_code, 400)

    def test_notice_requirements_seed_from_letter_and_verification_actor_is_server_owned(self):
        term = self.create_term()
        response = self.api.get(f"/api/allotment-requirements/?allotment={term['id']}")
        self.assertEqual(response.status_code, 200, response.content)
        rows = {row['kind']: row for row in response.data['results']}
        self.assertEqual(rows['police']['due_date'], '2026-01-31')
        self.assertEqual(rows['gst']['due_date'], '2026-04-01')
        self.assertEqual(rows['food']['status'], 'pending')
        stranger = User.objects.create_user('different-verifier')
        response = self.api.patch(f"/api/allotment-requirements/{rows['police']['id']}/", {
            'submitted_on': '2026-11-12', 'submission_reference': 'Police file',
            'verified_on': '2026-11-13', 'verified_by': stranger.pk,
            'change_reason': 'Check submitted document'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['verified_by'], self.user.pk)

    def test_attention_includes_expiry_today_and_90_days_but_not_91(self):
        for index, end in enumerate(['2026-11-13', '2027-02-11', '2027-02-12']):
            entry = Tenant.objects.create(name=f'Boundary {index}', type='Shop')
            self.create_term(tenant=entry.pk, end_date=end, exception_reference='Approved test term')
        response = self.api.get('/api/estate/attention/?kind=ending')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual({row['end_date'] for row in response.data['results']}, {'2026-11-13', '2027-02-11'})
        self.assertTrue(all(row['as_of'] == '2026-11-13' for row in response.data['results']))

    def test_retirement_and_protected_history_deactivate_instead_of_erasing_allottee(self):
        term = self.create_term()
        response = self.api.get(f'/api/tenants/{self.tenant.pk}/deletion-preview/')
        self.assertEqual(response.status_code, 200, response.content)
        response = self.api.delete(f'/api/tenants/{self.tenant.pk}/', {
            'change_reason': 'Allottee no longer active', 'confirmation': response.data['confirmation']}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.active)
        self.assertTrue(self.Allotment.objects.filter(pk=term['id']).exists())

    def test_admin_has_allotment_list_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/admin/estate_app/shop/').status_code, 403)
        self.assertEqual(self.client.get('/admin/estate_app/allotment/').status_code, 200)

    def test_admin_verification_records_the_acting_user(self):
        term = self.create_term()
        Requirement = apps.get_model('estate_app', 'AllotmentRequirement')
        requirement = Requirement.objects.get(allotment_id=term['id'], kind='police')
        self.client.force_login(self.user)
        response = self.client.post(f'/admin/estate_app/allotmentrequirement/{requirement.pk}/change/', {
            'allotment': term['id'], 'kind': 'police', 'applicable': 'on', 'due_date': '2026-01-31',
            'submitted_on': '2026-11-12', 'submission_reference': 'Police evidence',
            'verified_on': '2026-11-13', 'change_reason': 'Verify police record', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        requirement.refresh_from_db()
        self.assertEqual(requirement.verified_by_id, self.user.pk)

    def test_admin_creation_seeds_the_same_award_requirements_as_api(self):
        self.client.force_login(self.user)
        response = self.client.post('/admin/estate_app/allotment/add/', {
            **self.payload(rent_basis='area'), '_save': 'Save', 'change_reason': 'Record the award'})
        self.assertEqual(response.status_code, 302)
        term = self.Allotment.objects.get(tenant=self.tenant, shop__isnull=True)
        self.assertEqual(set(term.requirements.values_list('kind', flat=True)), {'police', 'gst', 'food'})

    def test_missing_food_licence_remains_actionable(self):
        self.create_term()
        response = self.api.get('/api/estate/attention/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row['kind'] == 'requirement' and row['requirement_kind'] == 'food'
                            for row in response.data['results']))
        self.assertFalse(any(row['kind'] == 'availability_unknown' for row in response.data['results']))

    def test_another_original_award_cannot_reuse_the_same_award_reference(self):
        self.create_term()
        response = self.api.post('/api/allotments/', self.payload(letter_issued_on='2027-01-01',
            start_date='2027-01-01', end_date='2027-12-31'), format='json')
        self.assertEqual(response.status_code, 400, response.content)

    def test_expired_unvacated_terms_precede_undated_document_actions(self):
        from estate_app.models import SystemSettings

        self.create_term(end_date='2026-06-30', possession_date='2026-01-01', possession_reference='Possession memo')
        response = self.api.get('/api/estate/attention/')
        self.assertFalse(any(row['kind'] == 'expired_unvacated' for row in response.data['results']))
        settings, _ = SystemSettings.objects.get_or_create(pk=1)
        settings.allotment_details_enabled = True
        settings.save(update_fields=['allotment_details_enabled'])
        response = self.api.get('/api/estate/attention/')
        self.assertEqual(response.data['results'][0]['kind'], 'expired_unvacated')
