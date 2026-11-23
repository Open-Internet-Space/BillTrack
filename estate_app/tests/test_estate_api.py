import datetime as dt
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from estate_app.models import Tenant


class EstateApiTests(TestCase):
    def setUp(self):
        self.enterContext(patch('django.utils.timezone.localdate', return_value=dt.date(2026, 11, 13)))
        self.user = User.objects.create_superuser('estate-admin', 'estate@example.invalid', 'Synthetic-estate-83!')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.tenant = Tenant.objects.create(name='Estate API allottee', type='Shop')
        self.Shop = apps.get_model('estate_app', 'Shop')
        self.Allotment = apps.get_model('estate_app', 'Allotment')
        self.shop = self.Shop.objects.create(code='A-101', name='Snacks', category='day_food')

    def payload(self, **changes):
        values = dict(shop=self.shop.pk, tenant=self.tenant.pk, source_notice='368/2025',
                      award_reference='Synthetic award', letter_issued_on='2026-01-01',
                      start_date='2026-01-01', end_date='2026-12-31', actual_area='150',
                      measurement_reference='Measurement memo')
        values.update(changes)
        return values

    def create_term(self, **changes):
        response = self.api.post('/api/allotments/', self.payload(**changes), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.data

    def test_authentication_and_searchable_paginated_shops(self):
        response = APIClient().get('/api/shops/')
        self.assertIn(response.status_code, [401, 403])
        response = self.api.get('/api/shops/?search=A-101')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['occupancy_status'], 'unknown')

    def test_api_validates_overlap_and_preserves_change_reasons(self):
        term = self.create_term()
        self.assertEqual(term['tenant_name'], self.tenant.name)
        self.assertEqual(term['shop_code'], 'A-101')
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
            shop = self.Shop.objects.create(code=f'A-{index+201}', name=f'Boundary {index}', category='utility')
            self.create_term(shop=shop.pk, end_date=end, exception_reference='Approved test term')
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
        response = self.api.get(f'/api/shops/{self.shop.pk}/deletion-preview/')
        self.assertEqual(response.status_code, 400, response.content)

    def test_admin_has_estate_lists(self):
        self.client.force_login(self.user)
        response = self.client.get('/admin/estate_app/shop/')
        self.assertContains(response, 'A-101')
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
            **self.payload(), '_save': 'Save', 'change_reason': 'Record the award'})
        self.assertEqual(response.status_code, 302)
        term = self.Allotment.objects.get(shop=self.shop)
        self.assertEqual(set(term.requirements.values_list('kind', flat=True)), {'police', 'gst', 'food'})

    def test_missing_food_licence_and_unknown_availability_remain_actionable(self):
        self.create_term()
        response = self.api.get('/api/estate/attention/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row['kind'] == 'requirement' and row['requirement_kind'] == 'food'
                            for row in response.data['results']))
        self.assertTrue(any(row['kind'] == 'availability_unknown' and row['shop'] == self.shop.pk
                            for row in response.data['results']))

    def test_another_original_award_cannot_reuse_the_same_award_reference(self):
        self.create_term()
        response = self.api.post('/api/allotments/', self.payload(letter_issued_on='2027-01-01',
            start_date='2027-01-01', end_date='2027-12-31'), format='json')
        self.assertEqual(response.status_code, 400, response.content)

    def test_expired_unvacated_terms_precede_undated_document_actions(self):
        self.shop.availability_confirmed_on = dt.date(2026, 1, 1)
        self.shop.availability_reference = 'Availability memo'
        self.shop.save()
        self.create_term(end_date='2026-06-30', possession_date='2026-01-01', possession_reference='Possession memo')
        response = self.api.get('/api/estate/attention/')
        self.assertEqual(response.data['results'][0]['kind'], 'expired_unvacated')
