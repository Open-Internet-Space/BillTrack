"""Deposit requirements and held liability; rent collections remain separate."""
import datetime as dt
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from django.core.exceptions import ValidationError


SECURITY_FIELDS = ('security_initial_rent', 'security_required_amount', 'security_due_date',
    'security_timing', 'security_offer_date',
    'security_requirement_reference', 'security_requirement_reason', 'security_extended_due_date',
    'security_extension_reference', 'refund_review_status', 'refund_review_reference', 'refund_review_reason',
    'security_last_operation_id')


def required_security(initial_monthly_rent):
    try:
        rent = Decimal(initial_monthly_rent)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('Record a positive reviewed initial monthly rent.')
    if not rent.is_finite() or rent <= 0:
        raise ValidationError('Record a positive reviewed initial monthly rent.')
    return (rent * 3 / 100).to_integral_value(rounding=ROUND_CEILING) * 100


def validate_security_timing(term):
    if term.security_timing == 'before':
        if not term.security_due_date or term.security_due_date > term.letter_issued_on:
            raise ValidationError('The pre-order deposit deadline must be on or before the allotment order date.')
        if term.security_offer_date and term.security_offer_date > term.security_due_date:
            raise ValidationError('The offer date cannot follow its deposit deadline.')
        if term.security_extended_due_date and term.security_extended_due_date > term.letter_issued_on:
            raise ValidationError('A pre-order deadline extension cannot follow the allotment order date.')
    elif term.security_offer_date:
        raise ValidationError('Record an offer date here only for a pre-order deposit.')


def validate_security_requirement(term, previous):
    changed = any(getattr(previous, key) != getattr(term, key) for key in SECURITY_FIELDS) if previous else any(
        getattr(term, key) not in (None, '', 'pending') for key in SECURITY_FIELDS)
    if not changed:
        if term.security_required_amount is not None:
            validate_security_timing(term)
        return
    actor = getattr(term, '_security_actor', None)
    if not (actor and actor.is_superuser and getattr(term, '_security_reason', '').strip()):
        raise ValidationError('Security requirements and refund clearance need a reviewed superuser action.')
    if term.renewal_of_id:
        raise ValidationError('Record security requirements only on the original award, including renewals in its chain.')
    if term.security_required_amount is None or term.security_initial_rent is None:
        raise ValidationError('Record both the initial monthly rent and approved required deposit.')
    if term.security_required_amount < required_security(term.security_initial_rent):
        raise ValidationError('The required deposit cannot be less than the reviewed three-month basis rounded up to a hundred.')
    if not term.security_requirement_reference.strip() or not term.security_requirement_reason.strip():
        raise ValidationError('Record the authority and reason for this security requirement.')
    if term.security_timing == 'before':
        term.security_due_date = term.security_due_date or term.letter_issued_on
    elif previous and previous.security_due_date and previous.security_timing == term.security_timing:
        if term.security_due_date != previous.security_due_date:
            raise ValidationError('Keep the original security deadline; record an approved extension separately.')
    else:
        original_due = term.letter_issued_on + dt.timedelta(days=7)
        if term.security_due_date and term.security_due_date != original_due:
            raise ValidationError('The original security deadline is seven days after the letter date.')
        term.security_due_date = original_due
    validate_security_timing(term)
    if bool(term.security_extended_due_date) != bool(term.security_extension_reference.strip()):
        raise ValidationError('An extended security deadline requires its approval reference and date together.')
    if term.security_extended_due_date and term.security_extended_due_date < term.security_due_date:
        raise ValidationError('An extended deadline cannot precede the original deadline.')
    if term.refund_review_status != 'pending' and (not term.refund_review_reference.strip() or not term.refund_review_reason.strip()):
        raise ValidationError('Refund clearance or an authorized exception requires an explicit reference and reason.')


def validate_security_pair(receipt, previous, target):
    protected = ('amount', 'payment_date', 'source', 'operation_id', 'recorded_by_id')
    protected += ('bill_id', 'penalty_paid') if target == 'bill' else ('charge_id',)
    if previous and previous.source == 'security_application' and any(
            getattr(previous, key) != getattr(receipt, key) for key in protected):
        raise ValidationError('A paired security settlement cannot be rewritten as an ordinary receipt correction.')
    if receipt.source != 'security_application':
        if receipt.operation_id:
            raise ValidationError('Ordinary receipts cannot claim a security operation ID.')
        return
    if previous and previous.source != 'security_application':
        raise ValidationError('An existing cash receipt cannot be converted into a security settlement.')
    if not previous and not getattr(receipt, '_security_authorized', False):
        raise ValidationError('Use the reviewed paired security application action.')
    if receipt.amount is None or (target == 'bill' and receipt.penalty_paid is None):
        return
    if target == 'bill' and not previous and receipt.bill_id and receipt.payment_date:
        bill = receipt.bill
        interest_available = min(bill.penalty,max(Decimal('0'),
            bill.accrued_penalty(receipt.payment_date)-bill.penalty_paid_after_start))
        if receipt.amount>bill.balance_due or receipt.penalty_paid>interest_available:
            raise ValidationError('Security may settle only unpaid principal and interest accrued by the actual application date.')
    from ..models import SecurityMovement
    movement = getattr(receipt, '_security_movement', None) if getattr(receipt, '_security_authorized', False) else None
    if movement is None:
        movement = SecurityMovement.objects.filter(operation_id=receipt.operation_id, kind='applied').first()
    total = receipt.amount + (receipt.penalty_paid if target == 'bill' else Decimal('0'))
    if movement is None or getattr(movement, f'applied_{target}_id') != getattr(receipt, f'{target}_id') or (
            movement.amount != total or movement.effective_date != receipt.payment_date
            or movement.recorded_by_id != receipt.recorded_by_id):
        raise ValidationError('The settlement must match its reviewed security movement, target, amount, date and actor.')
