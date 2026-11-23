from django.contrib import admin

from ..activity.admin import CorrectionAdminMixin
from ..admin_pagination import PaginationAdminMixin
from ..models import SecurityMovement


@admin.register(SecurityMovement)
class SecurityMovementAdmin(CorrectionAdminMixin,PaginationAdminMixin,admin.ModelAdmin):
    list_display = ['original_award','kind','amount','effective_date','reference','recorded_by']
    list_filter = ['kind','effective_date']
    search_fields = ['original_award__shop__code','original_award__tenant__name','reference','reason']
    autocomplete_fields = ['original_award']
    readonly_fields = ['uuid','kind','operation_id','applied_bill','applied_charge','recorded_by','created_at']
    list_select_related = ['original_award__shop','original_award__tenant','recorded_by']

    def has_change_permission(self,request,obj=None):
        return obj is None and super().has_change_permission(request,obj)

    def has_delete_permission(self,request,obj=None):
        return False

    def get_form(self,request,obj=None,**kwargs):
        base = super().get_form(request,obj,**kwargs)
        class ReceiptForm(base):
            def clean(self):
                data = super().clean()
                if self.instance._state.adding:
                    self.instance.kind = 'received'
                    self.instance.recorded_by = request.user
                return data
        return ReceiptForm

    def save_model(self,request,obj,form,change):
        obj.kind = 'received'
        obj.recorded_by = request.user
        obj.save()
