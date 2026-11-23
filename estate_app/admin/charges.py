from django.contrib import admin

from ..activity.admin import CorrectionAdminMixin
from ..admin_pagination import PaginationAdminMixin
from ..estate.charges import charge_queryset
from ..models import EstateCharge, EstateChargePayment


@admin.register(EstateCharge)
class EstateChargeAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    list_display=['allotment','kind','authority_reference','assessed_on','gross_amount','amount_paid',
                  'waiver_amount','balance_due','status','due_date']
    list_filter=['kind','due_date','allotment__shop']
    search_fields=['allotment__shop__code','allotment__tenant__name','authority_reference','description']
    autocomplete_fields=['allotment']
    readonly_fields=['uuid','gross_amount','amount_paid','balance_due','status','overdue','renewal_term',
        'waiver_amount','waiver_reference','waiver_reason','waived_by','waived_at','last_operation_id',
        'created_by','created_at','updated_at']

    def get_queryset(self,request):
        return charge_queryset()

    def get_readonly_fields(self,request,obj=None):
        return self.readonly_fields + (['allotment','kind','net_amount','tax_amount'] if obj else [])

    def has_delete_permission(self,request,obj=None):
        return False

    def save_model(self,request,obj,form,change):
        if not change:
            obj.created_by=request.user
        obj.save()


@admin.register(EstateChargePayment)
class EstateChargePaymentAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    list_display=['payment_date','charge','amount','receipt_reference','source','recorded_by']
    list_filter=['source','payment_date','charge__kind']
    search_fields=['charge__allotment__shop__code','charge__allotment__tenant__name','receipt_reference']
    autocomplete_fields=['charge']
    readonly_fields=['uuid','source','operation_id','recorded_by','created_at','updated_at']
    list_select_related=['charge__allotment__shop','recorded_by']

    def get_readonly_fields(self,request,obj=None):
        extra=['charge'] if obj else []
        if obj and obj.source!='receipt':
            extra+=['amount','payment_date','receipt_reference']
        return self.readonly_fields+extra

    def get_actions(self,request):
        actions=super().get_actions(request)
        actions.pop('delete_selected',None)
        return actions

    def has_delete_permission(self,request,obj=None):
        return bool(super().has_delete_permission(request,obj) and (obj is None or obj.source=='receipt'))

    def save_model(self,request,obj,form,change):
        if not change:
            obj.recorded_by=request.user
        obj.save()
