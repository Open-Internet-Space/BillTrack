from django.contrib import admin
from django.contrib import messages
from django import forms
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
import datetime
from urllib.parse import urlencode
from ..models import Tenant, Bill, Payment
from ..views import selected_bills_from_ids, selected_invoice_contexts
from ..admin_pagination import PaginationAdminMixin
from .common import ReceiptStatusFilter
from .common import delete_link
from .common import money


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1


class BillAdminForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = '__all__'
        labels = {'issue_date': 'Confirmed Receipt Date (Issue Date)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['due_date'].label = 'Due Date (calculated)' if self.instance.issue_date else 'Tentative Due Date'
        self.fields['due_date'].disabled = bool(self.instance.issue_date)
        self.fields['due_date'].help_text = 'Five calendar days after confirmed receipt; tentative dates do not start penalties.'


@admin.register(Bill)
class BillAdmin(PaginationAdminMixin, admin.ModelAdmin):
    form = BillAdminForm
    change_list_template = 'admin/estate_app/bill/change_list.html'
    actions = ['print_selected_bills']
    search_fields = ['invoice_no', 'dispatch_ref_no', 'tenant__name', 'notes']
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
        'gst_on_rent', 'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent',
        'status', 'receipt_status', 'receipt_reset_snapshot', 'created_at', 'updated_at'
    ]

    inlines = [PaymentInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
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
        tenants = Tenant.objects.filter(active=True).order_by('name')

        if request.method == 'POST':
            tenant_id = request.POST.get('tenant')
            from_period = request.POST.get('from_period')
            to_period = request.POST.get('to_period')

            try:
                tenant = tenants.get(pk=tenant_id)
                from_year, from_month = [int(part) for part in from_period.split('-')]
                to_year, to_month = [int(part) for part in to_period.split('-')]
                due_date = datetime.date.fromisoformat(request.POST.get('due_date'))
            except (AttributeError, TypeError, ValueError, Tenant.DoesNotExist):
                messages.error(request, 'Please select an allottee, valid month range, and due date.')
                return redirect('admin:estate_app_bill_bulk_add')

            start_index = from_year * 12 + from_month
            end_index = to_year * 12 + to_month
            if end_index < start_index:
                messages.error(request, 'To month must be after from month.')
                return redirect('admin:estate_app_bill_bulk_add')

            if end_index - start_index + 1 > 36:
                messages.error(request, 'Bulk bill creation is limited to 36 months at a time.')
                return redirect('admin:estate_app_bill_bulk_add')

            created_count = 0
            skipped_count = 0
            for index in range(start_index, end_index + 1):
                year = (index - 1) // 12
                month = (index - 1) % 12 + 1
                key = f'{year}-{month:02d}'

                if Bill.objects.filter(tenant=tenant, month=month, year=year).exists():
                    skipped_count += 1
                    continue

                Bill.objects.create(
                    tenant=tenant,
                    month=month,
                    year=year,
                    rent=request.POST.get('rent') or 0,
                    electric=request.POST.get(f'electric_{key}') or 0,
                    electric_reading=request.POST.get(f'electric_reading_{key}', ''),
                    water=request.POST.get('water') or 0,
                    gst_treatment=request.POST.get('gst_treatment') or 'cgst_sgst',
                    due_date=due_date,
                    notes=request.POST.get('notes', ''),
                    created_by=request.user,
                )
                created_count += 1

            messages.success(
                request,
                f'{created_count} bill(s) created. {skipped_count} duplicate month(s) skipped.'
            )
            return redirect('admin:estate_app_bill_changelist')

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Bulk add bills',
            'tenants': tenants,
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
