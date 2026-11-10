import json
import re
from django import forms
from django.contrib import admin
from django.contrib.admin.actions import delete_selected
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import QueryDict
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from urllib.parse import urlencode
from .context import current_operation
from .deletion import deletion_plan, confirmed
from ..models import ActivityEntry
from ..admin_pagination import PaginationAdminMixin


class ReasonForm(forms.Form):
    change_reason = forms.CharField(label='Reason for this change', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))


def apply_reason(reason):
    context = current_operation.get()
    if context is not None:
        context['reason'] = reason


class CorrectionAdminMixin:
    delete_confirmation_template = 'admin/activity_delete.html'
    delete_selected_confirmation_template = 'admin/activity_delete.html'

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST':
            apply_reason(request.POST.get('change_reason', '').strip() or 'Create record in Admin')
            if self.model._meta.label_lower == 'estate_app.bill' and object_id:
                from ..models import Payment
                obj = self.get_object(request, unquote(object_id))
                if not self.has_change_permission(request, obj):
                    raise PermissionDenied
                deleted_ids = [request.POST.get(key[:-6]+'id') for key, value in request.POST.items()
                               if re.fullmatch(r'payments-\d+-DELETE', key) and value]
                payments = list(Payment.objects.filter(pk__in=[pk for pk in deleted_ids if pk and pk.isdigit()], bill_id=object_id))
                if payments:
                    with transaction.atomic():
                        plan = deletion_plan(payments)
                        if not confirmed(request.POST.get('inline_confirmation'), plan):
                            return TemplateResponse(request, 'admin/activity_inline_delete.html', {
                                **self.admin_site.each_context(request), **plan, 'title': 'Confirm inline deletions',
                                'posted_fields': [(key, value) for key, values in request.POST.lists()
                                                  for value in values if key not in ('csrfmiddlewaretoken', 'inline_confirmation')],
                            })
                        return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        base = kwargs.pop('form', self.form)
        form = type('CorrectionForm', (base,), {'change_reason': forms.CharField(
            label='Reason for this change', max_length=2000, required=bool(obj), widget=forms.Textarea(attrs={'rows': 3}))})
        result = super().get_form(request, obj, form=form, **kwargs)
        return result

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if not any('change_reason' in str(options['fields']) for _, options in fieldsets):
            fieldsets.append(('Correction reason', {'fields': ('change_reason',)}))
        return fieldsets

    def save_model(self, request, obj, form, change):
        apply_reason(form.cleaned_data.get('change_reason') or 'Create record in Admin')
        return super().save_model(request, obj, form, change)

    def _delete_view(self, request, object_id, extra_context):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return super()._delete_view(request, object_id, extra_context)
        plan = deletion_plan([obj])
        form = ReasonForm(request.POST if request.method == 'POST' else None)
        valid = request.method == 'POST' and form.is_valid() and confirmed(request.POST.get('confirmation'), plan)
        if valid:
            apply_reason(form.cleaned_data['change_reason'])
            return super()._delete_view(request, object_id, extra_context)
        if request.method == 'POST' and form.is_valid():
            form.add_error(None, 'Affected records changed or confirmation expired. Review the current list and confirm again.')
        original = request.POST
        request.POST = QueryDict('')
        try:
            return super()._delete_view(request, object_id, {**(extra_context or {}), **plan, 'reason_form': form})
        finally:
            request.POST = original

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            actions['delete_selected'] = (type(self).corrected_delete_selected, 'delete_selected', actions['delete_selected'][2])
        return actions

    @admin.action(permissions=['delete'], description='Delete selected records')
    def corrected_delete_selected(self, request, queryset):
        with transaction.atomic():
            plan = deletion_plan(queryset)
            form = ReasonForm(request.POST if request.POST.get('post') else None)
            if request.POST.get('post') and form.is_valid() and confirmed(request.POST.get('confirmation'), plan):
                apply_reason(form.cleaned_data['change_reason'])
                return delete_selected(self, request, queryset)
            if request.POST.get('post') and form.is_valid():
                form.add_error(None, 'Affected records changed or confirmation expired. Review and confirm again.')
            original = request.POST
            request.POST = request.POST.copy()
            request.POST.pop('post', None)
            try:
                response = delete_selected(self, request, queryset)
            finally:
                request.POST = original
            response.context_data.update(plan, reason_form=form, bulk=True)
            return response

    def history_view(self, request, object_id, extra_context=None):
        if request.user.is_superuser:
            from django.shortcuts import redirect
            return redirect(reverse('admin:estate_app_activityentry_changelist')+'?'+urlencode({
                'record_type': self.model._meta.label_lower, 'record_id': unquote(object_id)}))
        return super().history_view(request, object_id, extra_context)


@admin.register(ActivityEntry)
class ActivityEntryAdmin(PaginationAdminMixin, admin.ModelAdmin):
    list_display = ['timestamp', 'actor_name', 'source', 'action', 'record_type', 'record_id', 'reason']
    list_filter = ['timestamp', 'actor_name', 'record_type', 'action']
    search_fields = ['actor_name', 'record_type', 'record_id', 'record_identity', 'reason', 'before', 'after']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp', 'actor_id', 'actor_name', 'source', 'operation_id', 'action', 'reason',
                       'record_type', 'record_id', 'record_identity', 'before_values', 'after_values', 'record_history']
    fields = readonly_fields
    actions = None

    def has_module_permission(self, request): return request.user.is_superuser
    def has_view_permission(self, request, obj=None): return request.user.is_superuser
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    @admin.display(description='Before values')
    def before_values(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.before, indent=2, ensure_ascii=False))

    @admin.display(description='After values')
    def after_values(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.after, indent=2, ensure_ascii=False))

    @admin.display(description='Record history')
    def record_history(self, obj):
        query = urlencode({'record_type': obj.record_type, 'record_identity': obj.record_identity})
        return format_html('<a href="{}?{}">All activity for this record</a>', reverse('admin:estate_app_activityentry_changelist'), query)
