from ..activity.admin import CorrectionAdminMixin
from django.contrib import admin
from django.contrib import messages
from django import forms
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError as APIValidationError
from urllib.parse import urlencode
from ..models import Allotment, Tenant, Bill, Payment
from ..serializers import BillRangeSerializer, BillSerializer
from ..views import selected_bills_from_ids, selected_invoice_contexts
from ..admin_pagination import PaginationAdminMixin
from .common import ReceiptStatusFilter
from .common import delete_link
from .common import money
from ..estate.legacy import LegacyReviewForm, legacy_preview, legacy_confirm


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1
    readonly_fields = ['source','operation_id']

    def has_delete_permission(self,request,obj=None):
        return bool(super().has_delete_permission(request,obj) and not (
            obj and obj.payments.filter(source='security_application').exists()))


class BillAdminForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = '__all__'
        labels = {'issue_date': 'Confirmed Receipt Date (Issue Date)'}

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)
        self.fields['due_date'].label = 'Due Date (calculated)' if self.instance.issue_date else 'Tentative Due Date'
        self.fields['due_date'].disabled = bool(self.instance.issue_date)
        self.fields['due_date'].help_text = 'Five calendar days after confirmed receipt; tentative dates do not start penalties.'
        if self.instance.billing_policy == 'notices_368_369':
            self.fields['due_date'].label = 'Due date (raised + seven days)'
            self.fields['due_date'].disabled = True
            self.fields['due_date'].help_text = 'Draft until raised. Confirmed email dispatch and the deadline govern late interest.'
        for field in ('billing_policy', 'dispatch_sender', 'rent_revision'):
            if field in self.fields:
                self.fields[field].disabled = True
        self.fields['billing_policy'].help_text = 'New bill policy is selected from its governing allotment.'
        if self.instance.pk:
            for field in ('tenant', 'allotment', 'billing_category', 'billing_policy'):
                self.fields[field].disabled = True
        else:
            self.initial['billing_category'] = 'allotment'
        self.fields['rent'].disabled = not self.instance.pk or self.instance.full_month_rent is not None
        self.fields['full_month_rent'].required = False
        self.fields['rent'].help_text = 'Net rent is calculated from full-month rent and inclusive holiday dates.'

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        fields = ('tenant', 'allotment', 'billing_category', 'year', 'month', 'rent', 'full_month_rent',
                  'electric', 'water', 'gst_treatment', 'holiday_start_date', 'holiday_end_date', 'notes',
                  'raised_date', 'email_dispatched_at', 'dispatch_recipient', 'dispatch_message_reference',
                  'rent_override_reason', 'rate_exception_reference')
        payload = {key: data[key] for key in fields if key in data}
        for key in ('tenant', 'allotment'):
            payload[key] = payload[key].pk if payload.get(key) else None
        if not self.instance.pk and payload.get('full_month_rent') is None:
            payload.pop('rent', None)
            payload.pop('full_month_rent', None)
        if not self.request and any(payload.get(key) != getattr(self.instance, key) for key in (
                'email_dispatched_at', 'dispatch_recipient', 'dispatch_message_reference')):
            raise forms.ValidationError('Confirmed dispatch changes require the signed-in Admin request.')
        serializer = BillSerializer(self.instance if self.instance.pk else None, data=payload, partial=True,
                                    context={'request': self.request} if self.request else {})
        try:
            serializer.is_valid(raise_exception=True)
        except APIValidationError as exc:
            raise forms.ValidationError(str(exc.detail))
        data.update(serializer.validated_data)
        for key, value in serializer.validated_data.items():
            setattr(self.instance, key, value)
        return data


@admin.register(Bill)
class BillAdmin(CorrectionAdminMixin, PaginationAdminMixin, admin.ModelAdmin):
    form = BillAdminForm
    change_form_template = 'admin/estate_app/bill/change_form.html'
    change_list_template = 'admin/estate_app/bill/change_list.html'
    actions = ['print_selected_bills']
    search_fields = ['invoice_no', 'dispatch_ref_no', 'tenant__name', 'tenant__allotment_description', 'allotment__shop__code', 'notes']
    list_filter = ['status', ReceiptStatusFilter, 'tenant__type',
                   ('tenant', admin.RelatedOnlyFieldListFilter), 'year', 'month', 'due_date']
    date_hierarchy = 'issue_date'
    list_display = [
        'invoice_no_display', 'tenant', 'period',
        'rent_display', 'gst_display',
        'total_display', 'paid_display',
        'balance_display', 'status_badge', 'receipt_status', 'dispatch_ref_no', 'issue_date', 'due_date', delete_link
    ]

    readonly_fields = [
        'invoice_no',
        'dispatch_sender', 'rent_revision', 'rate_snapshot', 'area_snapshot', 'rent_revision_reference',
        'holiday_closed_days', 'holiday_waiver',
        'gst_on_rent', 'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent',
        'status', 'receipt_status', 'receipt_reset_snapshot', 'created_at', 'updated_at'
    ]

    inlines = [PaymentInline]

    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)

        class ActingBillForm(base):
            def __init__(self, *args, **form_kwargs):
                super().__init__(*args, request=request, **form_kwargs)

        return ActingBillForm

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/legacy-review/', self.admin_site.admin_view(self.legacy_review_view),
                 name='estate_app_bill_legacy_review'),
            path(
                'bulk-add/',
                self.admin_site.admin_view(self.bulk_add_view),
                name='estate_app_bill_bulk_add',
            ),
            path(
                'bulk-print/',
                self.admin_site.admin_view(self.bulk_print_view),
                name='estate_app_bill_bulk_print',
            ),
        ]
        return custom_urls + urls

    def legacy_review_view(self, request, object_id):
        if not request.user.is_superuser:
            raise PermissionDenied
        from django.shortcuts import get_object_or_404
        bill = get_object_or_404(Bill, pk=object_id)
        form = LegacyReviewForm(bill, request.POST or None)
        review = None
        if request.method == 'POST':
            try:
                if 'confirmation' in request.POST:
                    result = legacy_confirm(object_id, request.POST['confirmation'], request.user, 'admin')
                    messages.success(request, 'This review was already applied.' if result['already_applied']
                                     else 'Historical bill updated. The receipts were preserved.')
                    return redirect('admin:estate_app_bill_change', bill.pk)
                if form.is_valid():
                    review = legacy_preview(bill, request.POST.dict(), request.user)
            except (ValidationError, IntegrityError) as error:
                form.add_error(None, ' '.join(error.messages) if isinstance(error, ValidationError)
                               else 'The billing period has changed. Review the bill again.')
        return TemplateResponse(request, 'admin/estate_app/bill/legacy_review.html', {
            **self.admin_site.each_context(request), 'title': f'Review historical invoice {bill.invoice_no}',
            'form': form, 'review': review, 'bill': bill})

    @admin.action(description='Print selected bills')
    def print_selected_bills(self, request, queryset):
        selected_ids = ','.join(str(pk) for pk in queryset.values_list('pk', flat=True))
        url = reverse('admin:estate_app_bill_bulk_print')
        return redirect(f'{url}?{urlencode({"ids": selected_ids})}')

    def bulk_print_view(self, request):
        from ..views.invoices.branding import invoice_configuration_error
        error = invoice_configuration_error(request)
        if error is not None:
            return error
        raw_ids = request.GET.get('ids', '')
        try:
            selected_ids = [int(pk) for pk in raw_ids.split(',') if pk.strip()]
        except ValueError:
            selected_ids = []

        ordered_bills = selected_bills_from_ids(selected_ids)

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Print selected bills',
            'print_invoices': selected_invoice_contexts(ordered_bills),
        }
        return TemplateResponse(request, 'admin/estate_app/bill/bulk_print.html', context)

    def bulk_add_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        tenants = Tenant.objects.filter(active=True).order_by('name')

        if request.method == 'POST':
            try:
                from_year, from_month = map(int, request.POST.get('from_period', '').split('-'))
                to_year, to_month = map(int, request.POST.get('to_period', '').split('-'))
                start, end = from_year * 12 + from_month, to_year * 12 + to_month
                if not 1 <= end - start + 1 <= 36:
                    raise ValueError('Choose an ordered range of at most 36 months.')
                payload = request.POST.dict()
                for key in ('allotment', 'holiday_start_date', 'holiday_end_date', 'due_date', 'full_month_rent', 'raised_date'):
                    if not payload.get(key):
                        payload.pop(key, None)
                payload.update(from_year=from_year, from_month=from_month, to_year=to_year, to_month=to_month,
                    month_items=[{'year': (index - 1) // 12, 'month': (index - 1) % 12 + 1,
                        'electric': request.POST.get(f'electric_{(index - 1) // 12}-{(index - 1) % 12 + 1:02d}') or 0,
                        'electric_reading': request.POST.get(f'electric_reading_{(index - 1) // 12}-{(index - 1) % 12 + 1:02d}', '')}
                        for index in range(start, end + 1)])
                serializer = BillRangeSerializer(data=payload, context={'request': request})
                serializer.is_valid(raise_exception=True)
                created, skipped = serializer.save()
            except (ValueError, APIValidationError, ValidationError, IntegrityError) as exc:
                messages.error(request, f'No bills were created. {exc}')
            else:
                messages.success(request, f'{len(created)} bill(s) created. {len(skipped)} duplicate month(s) skipped.')
                return redirect('admin:estate_app_bill_changelist')

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Bulk add bills',
            'tenants': tenants,
            'allotments': Allotment.objects.select_related('shop', 'tenant').order_by('shop__code', '-start_date'),
            'data': request.POST,
            'electric_values': {key: value for key, value in request.POST.items() if key.startswith('electric')},
            'gst_choices': Bill.GST_TREATMENT_CHOICES,
        }
        return TemplateResponse(request, 'admin/estate_app/bill/bulk_add.html', context)

    # ── DISPLAY METHODS ─────────────────────────────

    def invoice_no_display(self, obj):
        if obj.invoice_no:
            return format_html('<span style="color:#f0a500;">{}</span>', obj.invoice_no)
        return format_html('<span style="color:red;">[Pending]</span>')
    invoice_no_display.short_description = 'Invoice No.'

    def period(self, obj):
        return f"{obj.get_month_name()} {obj.year}"
    period.short_description = 'Period'

    def rent_display(self, obj):
        return f"₹{money(obj.rent)}"
    rent_display.short_description = 'Rent (Base)'

    def gst_display(self, obj):
        if float(obj.gst_on_rent or 0) > 0:
            if obj.gst_treatment == 'igst':
                return format_html(
                    '<span style="color:orange;">₹{}</span><br>'
                    '<small style="color:#999;">IGST: ₹{}</small>',
                    money(obj.gst_on_rent),
                    money(obj.igst_on_rent),
                )
            return format_html(
                '<span style="color:orange;">₹{}</span><br>'
                '<small style="color:#999;">CGST: ₹{} | SGST: ₹{}</small>',
                money(obj.gst_on_rent),
                money(obj.cgst_on_rent),
                money(obj.sgst_on_rent),
            )
        return format_html('<span style="color:gray;">—</span>')
    gst_display.short_description = 'GST on Rent'

    def total_display(self, obj):
        return f"₹{money(obj.total_amount)}"
    total_display.short_description = 'Total Amount'

    def paid_display(self, obj):
        return f"₹{money(obj.amount_paid)}"
    paid_display.short_description = 'Amount Paid'

    def balance_display(self, obj):
        if float(obj.balance_due or 0) > 0:
            return format_html(
                '<span style="color:orange;">₹{}</span>',
                money(obj.balance_due)
            )
        return format_html('<span style="color:green;">₹0.00</span>')
    balance_display.short_description = 'Balance Due'

    def status_badge(self, obj):
        colors = {'Paid': 'green', 'Partial': 'orange', 'Unpaid': 'red'}
        return format_html(
            '<span style="background:{}; color:white; padding:3px 10px; border-radius:3px;">{}</span>',
            colors.get(obj.status, 'gray'), obj.status
        )
    status_badge.short_description = 'Status'

    # ── SAVE ────────────────────────────────────────
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.save()
