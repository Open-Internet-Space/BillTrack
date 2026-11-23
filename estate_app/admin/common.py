from django.contrib import admin
from django.db.models import Q
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
    title = 'email / receipt confirmation'
    parameter_name = 'receipt'

    def lookups(self, request, model_admin):
        return [('pending', 'Pending email / receipt'), ('confirmed', 'Confirmed email / receipt')]

    def queryset(self, request, queryset):
        if self.value() in ('pending', 'confirmed'):
            confirmed = (Q(billing_policy='legacy_receipt', issue_date__isnull=False)
                         | Q(billing_policy='notices_368_369', email_dispatched_at__isnull=False))
            return queryset.filter(confirmed) if self.value() == 'confirmed' else queryset.exclude(confirmed)
        return queryset
