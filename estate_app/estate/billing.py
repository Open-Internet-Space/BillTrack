"""Calendar-day rent waivers; monetary results are authoritative on the server."""
import calendar
import datetime as dt
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError


def holiday_rent(full_month_rent, year, month, start=None, end=None):
    try:
        amount = Decimal(str(full_month_rent))
        if not amount.is_finite() or not Decimal('0') <= amount <= Decimal('99999999.99'):
            raise InvalidOperation
        if amount != amount.quantize(Decimal('0.01')):
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({'full_month_rent': 'Enter a nonnegative amount with at most two decimal places.'})
    if not isinstance(year, int) or not isinstance(month, int) or not 2000 <= year <= 2100 or not 1 <= month <= 12:
        raise ValidationError('Choose a valid billing month and year (2000–2100).')
    if (start is None) != (end is None):
        raise ValidationError({'holiday_end_date': 'Enter both holiday dates or clear both.'})
    if start is not None and (type(start) is not dt.date or type(end) is not dt.date or end < start):
        raise ValidationError({'holiday_end_date': 'Holiday end must be on or after its start date.'})
    days = calendar.monthrange(year, month)[1]
    first, last = dt.date(year, month, 1), dt.date(year, month, days)
    closed = max(0, (min(end, last) - max(start, first)).days + 1) if start else 0
    rent = (amount * (days - closed) / days).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {'days_in_month': days, 'closed_days': closed, 'waiver_amount': amount - rent, 'applicable_rent': rent}


def annual_revisions(rate, as_of, through):
    rate = Decimal(str(rate))
    if not rate.is_finite() or rate <= 0 or rate != rate.quantize(Decimal('0.0001')):
        raise ValidationError({'rate': 'Enter a positive rate with at most four decimal places.'})
    if type(as_of) is not dt.date or type(through) is not dt.date:
        raise ValidationError('Record actual rate as-of and preview dates.')
    if not 2000 <= through.year <= 2100:
        raise ValidationError('Choose a preview date between 2000 and 2100.')
    revisions = []
    for year in range(max(2026, as_of.year), through.year + 1):
        day = dt.date(year, 4, 1)
        if as_of < day <= through:
            rate = (rate * Decimal('1.05')).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            revisions.append({'effective_date': day, 'rate': rate})
    return revisions


def rent_schedule(term, year, month):
    holiday_rent(0, year, month)
    through = dt.date(year, month, calendar.monthrange(year, month)[1])
    revision = term.original_award.rent_revisions.filter(effective_date__lte=through).order_by('-effective_date').first()
    if revision is None:
        raise ValidationError({'rent_revision': 'Record the accepted rate and its as-of date on the original award.'})
    proposed = annual_revisions(revision.rate, revision.effective_date, through)
    return {'revision_id': revision.pk, 'rate': revision.rate, 'area': term.actual_area,
            'approval_reference': revision.approval_reference,
            'full_month_rent': (revision.rate * term.actual_area).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'missing_revision_dates': [item['effective_date'] for item in proposed],
            'proposed_rate': proposed[-1]['rate'] if proposed else revision.rate}


def notice_interest(principal, start, as_of, principal_payments):
    """12% simple actual/365; dated receipts reduce principal, never accrued interest."""
    if start is None or as_of <= start:
        return Decimal('0.00')
    balance, interest, previous = Decimal(principal), Decimal('0'), start
    for day, amount in sorted(principal_payments, key=lambda item: item[0]):
        if day > as_of:
            break
        if day > previous:
            interest += balance * Decimal('0.12') * (day - previous).days / 365
            previous = day
        balance = max(Decimal('0'), balance - amount)
    interest += balance * Decimal('0.12') * (as_of - previous).days / 365
    return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
