from ..activity.admin import CorrectionAdminMixin
from django.contrib import admin
from django.utils.html import format_html
from ..models import Payment
from ..admin_pagination import PaginationAdminMixin
from .common import money


@admin.register(Payment)
class PaymentAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    readonly_fields = ['source', 'operation_id']

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (['bill', 'amount', 'penalty_paid', 'payment_date', 'recorded_by']
                                      if obj and obj.source != 'receipt' else [])

    def has_delete_permission(self, request, obj=None):
        return bool(super().has_delete_permission(request, obj) and (obj is None or obj.source == 'receipt'))

    list_display = ['payment_date', 'bill', 'amount_display']
    search_fields = ['receipt_no', 'bill__invoice_no', 'bill__dispatch_ref_no', 'bill__tenant__name', 'bill__tenant__allotment_description', 'notes']
    list_filter = ['bill__tenant__type', ('bill__tenant', admin.RelatedOnlyFieldListFilter),
                   'bill__year', 'bill__month', 'bill__status']
    date_hierarchy = 'payment_date'

    def amount_display(self, obj):
        return format_html(
            '<strong style="color:green;">₹{}</strong>',
            money(obj.amount)
        )
    amount_display.short_description = 'Amount Received'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        obj.save()
