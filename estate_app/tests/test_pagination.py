from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import TokenProxy

from ..models import Tenant


class AdminPaginationTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('pager', 'pager@example.com', 'password'))
        Tenant.objects.bulk_create([Tenant(name=f'Tenant {index:02}', type='Shop', gst_applicable=False)
                                    for index in range(32)])
        self.url = reverse('admin:estate_app_tenant_changelist')

    def test_pages_and_row_choices_preserve_search(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['cl'].result_list), 10)
        self.assertContains(response, 'Rows per page')
        response = self.client.get(self.url, {'page_size': 15, 'p': 2, 'q': 'Tenant'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['cl'].result_list), 15)
        self.assertContains(response, 'Showing 16-30 of 32')
        self.assertContains(response, 'Tenant 15')
        self.assertEqual(response.context['cl'].params['q'], 'Tenant')
        self.assertEqual(response.context['cl'].get_filters_params(), {})
        previous = self.client.get(self.url + response.context['cl'].previous_page_url)
        following = self.client.get(self.url + response.context['cl'].next_page_url)
        self.assertEqual(previous.context['cl'].page_num, 1)
        self.assertEqual(following.context['cl'].page_num, 3)
        self.assertEqual(len(following.context['cl'].result_list), 2)

    def test_invalid_sizes_fall_back_without_orm_lookups(self):
        for size in ('bad', '0', '-1', '100000', '11'):
            response = self.client.get(self.url, {'page_size': size})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context['cl'].result_list), 10)

    def test_stale_pages_clamp_after_deletion_filtering_and_empty_results(self):
        Tenant.objects.filter(name__gte='Tenant 10').delete()
        for query, count in (({'p': 2}, 10), ({'p': 2, 'q': 'missing'}, 0), ({'p': -1}, 10)):
            response = self.client.get(self.url, query)
            self.assertEqual(response.status_code, 200)
            cl = response.context['cl']
            self.assertEqual(cl.page_num, 1)
            self.assertEqual(len(cl.result_list), count)
            self.assertEqual(cl.page_start, 1 if count else 0)
            self.assertIsNone(cl.previous_page_url)
            self.assertIsNone(cl.next_page_url)

    def test_out_of_range_page_clamps_to_last_page(self):
        response = self.client.get(self.url, {'p': 100, 'q': 'Tenant', 'page_size': 15})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cl'].page_num, 3)
        self.assertEqual(len(response.context['cl'].result_list), 2)

    def test_every_registered_admin_uses_pagination_including_token_urls(self):
        for model, model_admin in admin.site._registry.items():
            url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
            response = self.client.get(url, {'page_size': 15})
            self.assertEqual(response.status_code, 200, model._meta.label)
            self.assertEqual(response.context['cl'].list_per_page, 15, model._meta.label)
        token_admin = admin.site._registry[TokenProxy]
        from rest_framework.authtoken.admin import TokenChangeList
        self.assertTrue(issubclass(token_admin.get_changelist(None), TokenChangeList))
