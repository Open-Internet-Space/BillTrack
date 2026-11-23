"""Generate plain-text snapshots without touching dispatch or reminder state."""
from decimal import Decimal
from django.core.exceptions import ValidationError as ModelValidationError
from string import Formatter
from .validation import validate_header
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from ..models import Bill, Tenant, SystemSettings
from ..views.bills import bill_read_queryset

def generate(allottee_id,bill_ids,template):
    bills=list(bill_read_queryset().filter(pk__in=bill_ids).order_by('year','month','pk'))
    if len(bills)!=len(bill_ids):
        raise ValidationError('A selected bill no longer exists. Refresh the bill selection.')
    if bills:
        tenant_id=bills[0].tenant_id
        if any(bill.tenant_id!=tenant_id for bill in bills) or (allottee_id and allottee_id!=tenant_id):
            raise ValidationError('Select bills belonging to one allottee only.')
        allottee=bills[0].tenant
    else:
        allottee=Tenant.objects.filter(pk=allottee_id).first()
        if not allottee:
            raise ValidationError('Choose an existing allottee.')
    config=SystemSettings.objects.first()
    lines=[]; total=Decimal('0')
    for bill in bills:
        if bill.is_draft:
            raise ValidationError('Raise the selected notice invoice before preparing a dues email.')
        principal=bill.balance_due; penalty=bill.penalty
        total+=principal+penalty
        due=str(bill.due_date) if bill.deadline_established else 'Receipt not confirmed; due date not established'
        evidence = f'Shop {bill.allotment.shop.code} | Award {bill.allotment.award_reference}\n' if bill.allotment_id else ''
        if bill.billing_policy == 'notices_368_369':
            evidence += f'Notices 368–369 | Raised {bill.raised_date} | Email dispatch: {bill.dispatch_day or "awaiting confirmation"}\n'
        lines.append(f'{bill.get_month_name()} {bill.year} | Reference: {bill.dispatch_ref_no or bill.invoice_no}\n'
                     f'{evidence}Due date: {due}\nRemaining principal: INR {principal:.2f}\n'
                     f'Remaining penalty: INR {penalty:.2f}\nOutstanding: INR {principal+penalty:.2f}')
    now=timezone.now()
    values={'allottee_name':allottee.name,'allotment_description':allottee.allotment_description,'organisation_name':config.letterhead_name if config else '',
            'signing_authority':config.signing_authority if config else '',
            'preparation_date':timezone.localtime(now).strftime('%d %b %Y'),
            'bill_details':'\n\n'.join(lines) or 'No bills selected.', 'outstanding_total':f'INR {total:.2f}'}
    try:
        template.full_clean()
        # Bound expanded text before allocating it, even with repeated bill_details placeholders.
        for text, limit in [(template.subject, 240), (template.body, 100000)]:
            length = sum(len(literal) + (len(values[name]) if name is not None else 0)
                         for literal, name, _, _ in Formatter().parse(text))
            if length > limit:
                raise ValidationError('The merged email is too long. Shorten the template or select fewer bills.')
        subject = template.subject.format_map(values)
        validate_header(subject)
    except ModelValidationError:
        raise ValidationError('Review the email template. Its subject must produce a single line and placeholders must be supported.')
    return {'allottee_id':allottee.pk,'allottee_name':allottee.name,'template_id':template.pk,
            'bill_ids':[bill.pk for bill in bills], 'to':'' if allottee.email_not_provided else allottee.email,
            'cc':config.email_draft_cc if config else '', 'subject':subject,
            'body':template.body.format_map(values),'calculated_at':now.isoformat()}
