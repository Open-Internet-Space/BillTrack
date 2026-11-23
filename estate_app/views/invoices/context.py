import calendar
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from ...models import Bill, SystemSettings
from .formatting import amount_to_words
from .formatting import format_money
from .branding import invoice_branding_context
from .formatting import round_rupees


NOTICE_NOTE = ('Payment is due within seven calendar days after raising the invoice. '
    'Late interest is 12% per annum simple interest on unpaid billed principal, using actual days / 365, '
    'only for days after the later of the deadline and confirmed email dispatch. '
    'GST applies to net rent after any holiday waiver.')


def invoice_context(bill, system_settings=None):
    # Normalize all display-ready invoice values in one place to keep HTML/PDF
    # templates "dumb" and predictable.
    gst_rate = Decimal(bill.tenant.get_gst_rate() or 0)
    half_gst_rate = gst_rate / 2
    total_amount_before_gst = bill.rent + bill.electric + bill.water
    total_penalty = bill.penalty + bill.previous_penalty
    excess_paid = max(Decimal('0'), bill.amount_paid - bill.total_amount)
    total_payable = max(Decimal('0'), bill.total_payable - excess_paid)
    invoice_date = bill.raised_date or bill.issue_date or bill.created_at.date()
    system_settings = system_settings if system_settings is not None else SystemSettings.get_settings()
    branding = invoice_branding_context(system_settings, bill.issue_date.year if bill.issue_date else bill.year)

    return {
        **branding,
        'bill': bill,
        'notice_policy': bill.billing_policy == 'notices_368_369',
        'policy_note': NOTICE_NOTE if bill.billing_policy == 'notices_368_369' else '',
        'shop_code': bill.allotment.shop.code if bill.allotment_id else '',
        'full_month_rent': format_money(bill.full_month_rent) if bill.full_month_rent is not None else None,
        'holiday_waiver': format_money(bill.holiday_waiver),
        'invoice_no': bill.invoice_no or f"Pending-{bill.id}",
        'dispatch_ref_no': bill.dispatch_ref_no or branding['reference_placeholder'],
        'invoice_date': invoice_date.strftime('%d %B %Y'),
        'billing_period': f"{bill.get_month_name()} {bill.year}",
        'due_date': bill.due_date.strftime('%d %B %Y') if bill.due_date else 'Draft — not raised',
        'days_in_month': calendar.monthrange(bill.year, bill.month)[1],
        'gst_rate': f"{format_money(gst_rate).rstrip('0').rstrip('.')}%" if gst_rate else 'Nil',
        'cgst_rate': f"{format_money(half_gst_rate).rstrip('0').rstrip('.')}%" if half_gst_rate else 'Nil',
        'sgst_rate': f"{format_money(half_gst_rate).rstrip('0').rstrip('.')}%" if half_gst_rate else 'Nil',
        'igst_rate': f"{format_money(gst_rate).rstrip('0').rstrip('.')}%" if gst_rate else 'Nil',
        'is_igst': bill.gst_treatment == 'igst',
        'gst_treatment_label': 'IGST' if bill.gst_treatment == 'igst' else 'CGST + SGST',
        'rent': format_money(bill.rent),
        'electric': format_money(bill.electric),
        'electric_reading': bill.electric_reading or 'as recorded in bill',
        'water': format_money(bill.water),
        'gst_on_rent': format_money(bill.gst_on_rent),
        'cgst': format_money(bill.cgst_on_rent),
        'sgst': format_money(bill.sgst_on_rent),
        'igst': format_money(bill.igst_on_rent),
        'rent_with_gst': format_money(bill.rent_with_gst),
        'total_amount': format_money(bill.total_amount),
        'total_amount_before_gst': format_money(total_amount_before_gst),
        'previous_balance': format_money(bill.previous_balance),
        'previous_penalty': format_money(bill.previous_penalty),
        'penalty': format_money(total_penalty),
        'amount_paid': format_money(bill.amount_paid_including_penalty),
        'excess_paid': format_money(excess_paid),
        'balance_due': format_money(bill.balance_due),
        'total_payable': format_money(total_payable),
        'rounded_total_payable': f"{round_rupees(total_payable):,.0f}",
        'amount_in_words': amount_to_words(total_payable),
        'rounded_amount_in_words': amount_to_words(round_rupees(total_payable)),
    }


def consolidated_invoice_context(bills, system_settings=None):
    # Carry-forward and invoice groups share the same person-and-term boundary.
    if not bills:
        return None

    groups = {(bill.tenant_id, bill.allotment_id, bill.is_draft) for bill in bills}
    if len(groups) != 1:
        return None

    ordered = sorted(bills, key=lambda bill: (bill.year, bill.month, bill.pk))
    selected_ids = {bill.pk for bill in ordered}
    tenant = ordered[0].tenant

    rent = sum((bill.rent for bill in ordered), Decimal('0'))
    electric = sum((bill.electric for bill in ordered), Decimal('0'))
    water = sum((bill.water for bill in ordered), Decimal('0'))
    gst_on_rent = sum((bill.gst_on_rent for bill in ordered), Decimal('0'))
    cgst = sum((bill.cgst_on_rent for bill in ordered), Decimal('0'))
    sgst = sum((bill.sgst_on_rent for bill in ordered), Decimal('0'))
    igst = sum((bill.igst_on_rent for bill in ordered), Decimal('0'))
    total_amount = sum((bill.total_amount for bill in ordered), Decimal('0'))
    amount_paid = sum((bill.amount_paid_including_penalty for bill in ordered), Decimal('0'))
    principal_paid = sum((bill.amount_paid for bill in ordered), Decimal('0'))
    balance_due = max(Decimal('0'), total_amount - principal_paid)
    excess_paid = max(Decimal('0'), principal_paid - total_amount)
    current_penalty = sum((bill.penalty for bill in ordered), Decimal('0'))

    today = timezone.localdate()
    last_bill = ordered[-1]
    system_settings = system_settings if system_settings is not None else SystemSettings.get_settings()
    branding = invoice_branding_context(system_settings, last_bill.issue_date.year if last_bill.issue_date else last_bill.year)
    previous_due_bills = Bill.objects.filter(
        tenant=tenant,
        allotment_id=last_bill.allotment_id,
        status__in=['Unpaid', 'Partial'],
        due_date__lt=today,
    ).filter(
        Q(billing_policy='legacy_receipt', issue_date__isnull=False)
        | Q(billing_policy='notices_368_369', raised_date__isnull=False)
    ).filter(
        Q(year__lt=last_bill.year) |
        Q(year=last_bill.year, month__lt=last_bill.month)
    ).exclude(pk__in=selected_ids).prefetch_related('payments')
    previous_balance = sum((bill.balance_due for bill in previous_due_bills), Decimal('0'))
    previous_penalty = sum((bill.penalty for bill in previous_due_bills), Decimal('0'))
    penalty = current_penalty + previous_penalty
    total_payable = max(Decimal('0'), balance_due + current_penalty + previous_balance + previous_penalty - excess_paid)

    first_period = f"{ordered[0].get_month_name()} {ordered[0].year}"
    last_period = f"{ordered[-1].get_month_name()} {ordered[-1].year}"
    billing_period = first_period if first_period == last_period else f"{first_period} - {last_period}"
    gst_rates = {Decimal(bill.tenant.get_gst_rate() or 0) for bill in ordered}
    gst_rate = gst_rates.pop() if len(gst_rates) == 1 else None
    half_gst_rate = gst_rate / 2 if gst_rate is not None else None
    treatments = {bill.gst_treatment for bill in ordered}
    due_dates = [bill.due_date for bill in ordered if bill.due_date]
    policies = {bill.billing_policy for bill in ordered}
    notice_policy = policies == {'notices_368_369'}
    mixed_policies = len(policies) > 1
    is_igst = treatments == {'igst'}
    gst_treatment_label = 'IGST' if is_igst else ('CGST + SGST' if treatments == {'cgst_sgst'} else 'Mixed')

    return {
        **branding,
        'tenant': tenant,
        'is_draft': all(bill.is_draft for bill in ordered),
        'notice_policy': notice_policy,
        'mixed_policies': mixed_policies,
        'policy_note': ('Mixed billing policies: each monthly line retains its own deadline and interest basis. '
            'Legacy receipt-policy lines retain the confirmed-receipt deadline. Notice-policy lines: ' + NOTICE_NOTE)
            if mixed_policies else NOTICE_NOTE if notice_policy else '',
        'shop_code': last_bill.allotment.shop.code if last_bill.allotment_id else '',
        'bills': ordered,
        'invoice_no': f"Consolidated ({billing_period})",
        'dispatch_ref_no': branding['reference_placeholder'],
        'invoice_date': timezone.localdate().strftime('%d %B %Y'),
        'billing_period': billing_period,
        'due_date': max(due_dates).strftime('%d %B %Y') if due_dates else 'Draft — not raised',
        'gst_rate': f"{format_money(gst_rate).rstrip('0').rstrip('.')}%" if gst_rate else ('Mixed' if gst_rate is None else 'Nil'),
        'cgst_rate': f"{format_money(half_gst_rate).rstrip('0').rstrip('.')}%" if half_gst_rate else ('Mixed' if half_gst_rate is None else 'Nil'),
        'sgst_rate': f"{format_money(half_gst_rate).rstrip('0').rstrip('.')}%" if half_gst_rate else ('Mixed' if half_gst_rate is None else 'Nil'),
        'igst_rate': f"{format_money(gst_rate).rstrip('0').rstrip('.')}%" if gst_rate else ('Mixed' if gst_rate is None else 'Nil'),
        'is_igst': is_igst,
        'gst_treatment_label': gst_treatment_label,
        'rent': format_money(rent),
        'electric': format_money(electric),
        'water': format_money(water),
        'gst_on_rent': format_money(gst_on_rent),
        'cgst': format_money(cgst),
        'sgst': format_money(sgst),
        'igst': format_money(igst),
        'rent_with_gst': format_money(rent + gst_on_rent),
        'total_amount': format_money(total_amount),
        'total_amount_before_gst': format_money(rent + electric + water),
        'previous_balance': format_money(previous_balance),
        'previous_penalty': format_money(previous_penalty),
        'penalty': format_money(penalty),
        'amount_paid': format_money(amount_paid),
        'excess_paid': format_money(excess_paid),
        'balance_due': format_money(balance_due),
        'total_payable': format_money(total_payable),
        'rounded_total_payable': f"{round_rupees(total_payable):,.0f}",
        'amount_in_words': amount_to_words(total_payable),
        'rounded_amount_in_words': amount_to_words(round_rupees(total_payable)),
        'line_items': [
            {
                'index': index,
                'period': f"{bill.get_month_name()} {bill.year}",
                'invoice_no': bill.invoice_no or f"Pending-{bill.id}",
                'policy_label': bill.get_billing_policy_display(),
                'due_date': bill.due_date.strftime('%d %b %Y') if bill.due_date else 'Draft — not raised',
                'rent': format_money(bill.rent),
                'full_month_rent': format_money(bill.full_month_rent) if bill.full_month_rent is not None else None,
                'holiday_waiver': format_money(bill.holiday_waiver),
                'holiday_closed_days': bill.holiday_closed_days,
                'days_in_month': calendar.monthrange(bill.year, bill.month)[1],
                'holiday_start_date': bill.holiday_start_date,
                'holiday_end_date': bill.holiday_end_date,
                'rate_snapshot': f'{bill.rate_snapshot:.4f}' if bill.rate_snapshot is not None else None,
                'area_snapshot': f'{bill.area_snapshot:.4f}' if bill.area_snapshot is not None else None,
                'rent_revision_reference': bill.rent_revision_reference,
                'notes': bill.notes,
                'electric_reading': bill.electric_reading,
                'electric': format_money(bill.electric),
                'water': format_money(bill.water),
                'gst_on_rent': format_money(bill.gst_on_rent),
                'total_amount': format_money(bill.total_amount),
            }
            for index, bill in enumerate(ordered, start=1)
        ],
    }
