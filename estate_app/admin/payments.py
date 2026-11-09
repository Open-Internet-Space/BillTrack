from django.contrib import admin
from django.utils.html import format_html
from ..models import Bill, Payment
from ..admin_pagination import PaginationAdminMixin
from .common import money


@admin.register(Payment)
class PaymentAdmin(PaginationAdminMixin, admin.ModelAdmin):
    list_display = ['payment_date', 'bill', 'amount_display']
    search_fields = ['receipt_no', 'bill__invoice_no', 'bill__dispatch_ref_no', 'bill__tenant__name', 'notes']
    list_filter = ['bill__tenant__type', ('bill__tenant', admin.RelatedOnlyFieldListFilter),
                   'bill__year', 'bill__month', 'bill__status']
    date_hierarchy = 'payment_date'

    def delete_model(self, request, obj):
        bill = obj.bill
        super().delete_model(request, obj)
        bill.update_status()

    def delete_queryset(self, request, queryset):
        bill_ids = list(queryset.values_list('bill_id', flat=True).distinct())
        super().delete_queryset(request, queryset)
        for bill in Bill.objects.filter(pk__in=bill_ids):
            bill.update_status()

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
