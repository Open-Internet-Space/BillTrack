from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html


def money(val):
    try:
        return f"{float(val):,.2f}"
    except:
        return "0.00"


def delete_link(obj):
    url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_delete', args=[obj.pk])
    return format_html('<a style="color:#dc2626;font-weight:700;" href="{}">Delete</a>', url)


class ReceiptStatusFilter(admin.SimpleListFilter):
    title = 'receipt status'
    parameter_name = 'receipt'

    def lookups(self, request, model_admin):
        return [('pending', 'Pending Receipt'), ('confirmed', 'Receipt Confirmed')]

    def queryset(self, request, queryset):
        if self.value() in ('pending', 'confirmed'):
            return queryset.filter(issue_date__isnull=self.value() == 'pending')
        return queryset
