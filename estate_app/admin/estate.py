from django.contrib import admin

from ..activity.admin import CorrectionAdminMixin
from ..admin_pagination import PaginationAdminMixin
from ..models import Allotment, AllotmentRequirement, RentRevision, Shop, SystemSettings
from ..estate.security import SECURITY_FIELDS


@admin.register(Shop)
class ShopAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'space_type', 'active', 'occupancy_status']
    list_filter = ['category', 'space_type', 'active']
    search_fields = ['code', 'name', 'location']
    readonly_fields = ['uuid', 'occupancy_status', 'created_at', 'updated_at']

    def has_module_permission(self, request):
        return SystemSettings.premises_are_enabled() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return SystemSettings.premises_are_enabled() and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return SystemSettings.premises_are_enabled() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return SystemSettings.premises_are_enabled() and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return SystemSettings.premises_are_enabled() and super().has_delete_permission(request, obj)


@admin.register(Allotment)
class AllotmentAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    list_display = ['tenant', 'award_reference', 'start_date', 'end_date', 'status', 'possession_date', 'handover_date']
    list_filter = ['source_notice', 'end_date']
    search_fields = ['tenant__allotment_description', 'tenant__name', 'award_reference', 'approval_reference']
    readonly_fields = ['uuid', 'status', 'extension_number', 'vacation_due_date', 'created_at', 'updated_at'] + list(SECURITY_FIELDS)
    def get_exclude(self, request, obj=None):
        return None if SystemSettings.premises_are_enabled() else ['shop']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'shop':
            form_field.label = 'Premises (optional)'
        return form_field

    autocomplete_fields = ['tenant', 'renewal_of']
    list_select_related = ['tenant']


@admin.register(RentRevision)
class RentRevisionAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    list_display = ['original_award', 'effective_date', 'rate', 'approval_reference']
    search_fields = ['original_award__shop__code', 'original_award__tenant__name', 'approval_reference']
    list_filter = ['effective_date']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    autocomplete_fields = ['original_award']
    list_select_related = ['original_award__shop', 'original_award__tenant']


@admin.register(AllotmentRequirement)
class RequirementAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    list_display = ['allotment', 'kind', 'due_date', 'status', 'submitted_on', 'verified_on', 'verified_by']
    list_filter = ['kind', 'applicable', 'due_date']
    search_fields = ['allotment__shop__code', 'allotment__tenant__name', 'submission_reference']
    readonly_fields = ['uuid', 'status', 'verified_by', 'created_at', 'updated_at']
    autocomplete_fields = ['allotment']
    list_select_related = ['allotment__shop', 'allotment__tenant', 'verified_by']

    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)

        class VerificationForm(base):
            def clean(self):
                data = super().clean()
                if 'verified_on' in self.changed_data:
                    self.instance.verified_by = request.user if data.get('verified_on') else None
                return data

        return VerificationForm

    def save_model(self, request, obj, form, change):
        if 'verified_on' in form.changed_data:
            obj.verified_by = request.user if obj.verified_on else None
        return super().save_model(request, obj, form, change)
