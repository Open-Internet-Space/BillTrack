from django.contrib.admin.options import IncorrectLookupParameters


PAGE_SIZES = (10, 15, 20, 25, 30)


class PageSizeChangeListMixin:
    def get_filters_params(self, params=None):
        filters = super().get_filters_params(params)
        filters.pop('page_size', None)
        return filters

    def get_results(self, request):
        size = request.GET.get('page_size', '10')
        self.list_per_page = int(size) if size in {str(n) for n in PAGE_SIZES} else 10
        self.list_max_show_all = 0
        self.page_num = max(1, self.page_num)
        try:
            super().get_results(request)
        except IncorrectLookupParameters:
            self.page_num = self.model_admin.get_paginator(request, self.queryset, self.list_per_page).num_pages
            super().get_results(request)
        self.page_num = min(self.page_num, self.paginator.num_pages)
        self.page_size_choices = PAGE_SIZES
        self.page_start = (self.page_num - 1) * self.list_per_page + 1 if self.result_count else 0
        self.page_end = min(self.page_num * self.list_per_page, self.result_count)
        self.previous_page_url = self.get_query_string({'p': self.page_num - 1}) if self.page_num > 1 else None
        self.next_page_url = self.get_query_string({'p': self.page_num + 1}) if self.page_num < self.paginator.num_pages else None


class PaginationAdminMixin:
    list_per_page = 10
    change_list_template = 'admin/paginated_change_list.html'

    def get_changelist(self, request, **kwargs):
        # Keep specialized admin behavior, including token-to-user change links.
        class PaginatedChangeList(PageSizeChangeListMixin, super().get_changelist(request, **kwargs)):
            pass
        return PaginatedChangeList
