from django.contrib import admin
from django.utils.html import format_html
from ..models import Tenant
from ..admin_pagination import PaginationAdminMixin


@admin.register(Tenant)
class TenantAdmin(PaginationAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'uuid', 'type', 'contact', 'email', 'gstin', 'last_billed_month', 'receipt_payment_period', 'active_badge']
    exclude = ['due_days']
    readonly_fields = ['receipt_payment_period', 'last_billed_month']
    search_fields = ['name', 'uuid', 'contact', 'email', 'gstin']
    list_filter = ['type', 'active', 'gst_applicable', 'penalty_type']

    def get_queryset(self, request):
        return Tenant.with_last_billed_month(super().get_queryset(request))

    @admin.display(description='Last billed month', ordering='_last_billed_period')
    def last_billed_month(self, obj):
        return obj.last_billed_month

    @admin.display(description='Payment period')
    def receipt_payment_period(self, obj):
        return '5 calendar days after confirmed receipt'

    class Media:
        js = ('estate_app/tenant_not_provided.js',)

    def active_badge(self, obj):
        if obj.active:
            return format_html('<span style="color:green;">● Active</span>')
        return format_html('<span style="color:red;">○ Inactive</span>')
    active_badge.short_description = 'Status'
