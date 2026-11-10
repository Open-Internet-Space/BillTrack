from ..activity.admin import CorrectionAdminMixin
from django.contrib import admin
from django import forms
from django.db import models
from django.utils.html import format_html
from ..models import SystemSettings
from ..admin_pagination import PaginationAdminMixin


@admin.register(SystemSettings)
class SystemSettingsAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    readonly_fields = ['logo_preview', 'updated_at', 'updated_by']
    formfield_overrides = {models.ImageField: {'widget': forms.FileInput}}
    fieldsets = [
        ('Letterhead', {'fields': ['letterhead_logo', 'logo_preview', 'letterhead_name',
                                  'letterhead_department', 'letterhead_address']}),
        ('Billed from', {'fields': ['billed_from', 'supplier_gstin', 'place_of_supply']}),
        ('Signing authority', {'fields': ['signing_authority']}),
        ('Invoice wording and reference', {'fields': ['reference_number_format', 'invoice_note', 'copy_to'],
                                          'description': 'Global wording applies whenever invoices are printed, including reprints of older bills. Use plain text and Enter for line breaks; HTML is not supported.'}),
        ('Payment information', {'fields': ['bank_details', 'invoice_remarks']}),
        ('Penalty calculation', {'fields': ['penalty_type', 'penalty_rate_pa', 'penalty_lumpsum', 'penalty_frequency']}),
        ('GST calculation', {'fields': ['gst_applicable', 'gst_rate', 'cgst_rate', 'sgst_rate']}),
        ('Manual email drafts', {'fields': ['email_draft_cc']}),
        ('Last updated', {'fields': ['updated_at', 'updated_by']}),
    ]

    @admin.display(description='Current logo')
    def logo_preview(self, obj):
        from ..views.invoices import invoice_logo_data_uri
        return format_html('<img src="{}" alt="Current letterhead logo" style="max-width:180px;max-height:100px">',
                           invoice_logo_data_uri(obj))

    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
