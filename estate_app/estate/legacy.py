"""Explicit review of one historical invoice. Existing receipt allocations are preserved."""
import datetime as dt
import hashlib
import json
import uuid

from django import forms
from django.contrib.auth.models import User
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ..activity.context import operation
from ..models import ActivityEntry, Allotment, Bill, RentRevision, SystemSettings


class LegacyReviewForm(forms.Form):
    allotment = forms.ModelChoiceField(queryset=Allotment.objects.none(), empty_label='Select the documented award')
    raised_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    email_dispatched_at = forms.DateTimeField(required=False, label='Confirmed email dispatch (India time)')
    dispatch_sender = forms.ModelChoiceField(queryset=User.objects.none(), required=False,
                                            label='Actual staff sender')
    dispatch_recipient = forms.EmailField(required=False)
    dispatch_message_reference = forms.CharField(max_length=250, required=False)
    rent_revision = forms.ModelChoiceField(queryset=RentRevision.objects.none(), required=False)
    rent_override_reason = forms.CharField(required=False, widget=forms.Textarea)
    rate_exception_reference = forms.CharField(max_length=250, required=False)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea)

    def __init__(self, bill, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bill = bill
        self.action = 'convert' if bill.allotment_id else 'link'
        if self.action == 'link':
            self.fields = {key: self.fields[key] for key in ('allotment', 'reason')}
            self.fields['allotment'].queryset = Allotment.objects.filter(tenant=bill.tenant).select_related('shop')
        else:
            del self.fields['allotment']
            self.fields['rent_revision'].queryset = bill.allotment.original_award.rent_revisions.all()
            self.fields['dispatch_sender'].queryset = User.objects.order_by('username')

    def clean(self):
        data = super().clean()
        if self.bill.billing_policy != 'legacy_receipt' or self.bill.billing_category == 'other':
            raise ValidationError('Select an unassigned or shop-linked historical bill using the legacy policy.')
        if self.data.get('action') != self.action:
            raise ValidationError('Review the current assignment and choose its available action.')
        if self.action == 'convert':
            evidence = [data.get(key) for key in ('email_dispatched_at', 'dispatch_sender',
                                                  'dispatch_recipient', 'dispatch_message_reference')]
            if any(evidence) and not all(evidence):
                raise ValidationError('Record the confirmed dispatch time, actual sender, recipient and message reference together.')
        return data


def review_state(bill):
    def money(amount):
        return f'{amount:.2f}'
    accrued = bill.accrued_penalty(timezone.localdate())
    return {'invoice': bill.invoice_no, 'period': f'{bill.year}-{bill.month:02}',
            'allottee': str(bill.tenant), 'award': str(bill.allotment) if bill.allotment_id else None,
            'allotment_id': bill.allotment_id, 'policy': bill.get_billing_policy_display(),
            'receipt_date': bill.issue_date, 'raised_date': bill.raised_date, 'due_date': bill.due_date,
            'dispatch_time': bill.email_dispatched_at, 'dispatch_sender': str(bill.dispatch_sender or ''),
            'dispatch_recipient': bill.dispatch_recipient, 'dispatch_reference': bill.dispatch_message_reference,
            'interest_start': bill.penalty_start_date, 'interest_accrued': money(accrued),
            'interest_due': money(max(0, accrued - bill.penalty_paid_after_start)),
            'principal': money(bill.total_amount), 'principal_paid': money(bill.amount_paid),
            'principal_due': money(bill.balance_due), 'interest_paid': money(sum(p.penalty_paid for p in bill.payments.all())),
            'rate_revision': bill.rent_revision_reference, 'rate': bill.rate_snapshot, 'area': bill.area_snapshot,
            'rent_override': bill.rent_override_reason, 'rate_exception': bill.rate_exception_reference}


def prepare_review(bill, raw):
    form = LegacyReviewForm(bill, raw)
    if not form.is_valid():
        raise ValidationError(form.errors.as_data())
    data = form.cleaned_data
    settings = SystemSettings.objects.first() or SystemSettings()
    bill._penalty_config = bill.tenant.get_penalty_config(settings)
    before = review_state(bill)
    term = data.get('allotment') or bill.allotment
    if form.action == 'link':
        if Bill.objects.filter(allotment=term, year=bill.year, month=bill.month).exclude(pk=bill.pk).exists():
            raise ValidationError('This allotment already has a bill for the selected month.')
        bill.allotment = term
        bill.billing_category = 'allotment'
        fields = ('allotment_id', 'billing_category')
    else:
        bill.billing_policy = 'notices_368_369'
        bill.issue_date = None
        for key in ('raised_date', 'email_dispatched_at', 'dispatch_sender', 'dispatch_recipient',
                    'dispatch_message_reference', 'rent_override_reason', 'rate_exception_reference'):
            setattr(bill, key, data[key])
        bill.due_date = bill.raised_date + dt.timedelta(days=7)
        if any(not bill.raised_date <= p.payment_date <= timezone.localdate() for p in bill.payments.all()):
            raise ValidationError('A retained receipt falls outside the proposed invoice dates.')
        if bill.full_month_rent is None:
            bill.full_month_rent = bill.rent
        bill.prepare_notice_rent(refresh=True)
        chosen = data['rent_revision']
        if bill.rent_revision_id != (chosen.pk if chosen else None):
            raise ValidationError('Explicitly select the applicable approved rate revision for this billing month.')
        fields = ('billing_policy', 'issue_date', 'raised_date', 'due_date', 'email_dispatched_at',
                  'dispatch_sender_id', 'dispatch_recipient', 'dispatch_message_reference', 'full_month_rent',
                  'rent_revision_id', 'rate_snapshot', 'area_snapshot', 'rent_revision_reference',
                  'rent_override_reason', 'rate_exception_reference')
    bill.clean(allotment=term)
    after = review_state(bill)
    receipts = list(bill.payments.order_by('pk').values())
    state = [before, after, timezone.localdate(), Bill.objects.filter(pk=bill.pk).values().get(),
             receipts, term.uuid, term.shop.uuid, term.award_reference, term.start_date, term.effective_end,
             list(term.original_award.rent_revisions.order_by('pk').values()), bill.tenant.uuid, bill._penalty_config]
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return {'before': before, 'after': after, 'receipts': [
        {key: p[key] for key in ('id','receipt_no','payment_date','amount','penalty_paid','source')} for p in receipts],
        'reason': data['reason']}, digest, fields


def legacy_preview(bill, raw, user):
    if not user.is_superuser:
        raise PermissionDenied
    review, digest, _ = prepare_review(bill, raw)
    keys = set(LegacyReviewForm.base_fields) | {'action'}
    token = {'actor': user.pk, 'bill': bill.pk, 'data': {k: raw.get(k) for k in keys if k in raw},
             'digest': digest, 'operation': uuid.uuid4().hex}
    return {**review, 'confirmation': signing.dumps(token, salt='estate-legacy-review', compress=True)}


@transaction.atomic
def legacy_confirm(pk, confirmation, user, source):
    if not user.is_superuser:
        raise PermissionDenied
    try:
        token = signing.loads(confirmation, salt='estate-legacy-review', max_age=600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('The confirmation is invalid or expired. Preview the bill again.')
    if token['actor'] != user.pk:
        raise PermissionDenied
    if str(token['bill']) != str(pk):
        raise ValidationError('This review is for a different bill.')
    rows = Bill.objects.filter(pk=pk)
    rows.update(status=F('status'))
    if ActivityEntry.objects.filter(operation_id=token['operation'], actor_id=user.pk,
                                    record_type='estate_app.bill', record_id=str(pk)).exists():
        return {'already_applied': True}
    bill = rows.first()
    if bill is None:
        raise ValidationError('This bill was removed. Review the current register.')
    review, digest, fields = prepare_review(bill, token['data'])
    if token['digest'] != digest:
        raise ValidationError('The bill, receipts or award evidence changed. Review the updated figures.')
    with operation(actor=user, reason=review['reason'], source=source) as context:
        context['operation_id'] = token['operation']
        # Apply only reviewed columns. Ordinary Bill.save can recalculate historical tax on rent changes.
        rows.update(**{key: getattr(bill, key) for key in fields})
        if token['data']['action'] == 'convert':
            bill.update_status()
    return {'already_applied': False}
