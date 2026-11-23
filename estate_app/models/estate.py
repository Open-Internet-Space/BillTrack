"""Shop identity, contractual terms and physical possession are separate records."""
import calendar
import datetime as dt
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, router, transaction
from django.db.models.functions import Lower
from django.utils import timezone


def calendar_months(day, months):
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    return dt.date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def yearly_end(day):
    try:
        anniversary = day.replace(year=day.year + 1)
    except ValueError:  # A leap-day award remains valid through the next 28 February.
        anniversary = dt.date(day.year + 1, 3, 1)
    return anniversary - dt.timedelta(days=1)


class Shop(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=50, validators=[RegexValidator(
        r'\A[A-Z0-9][A-Z0-9._/-]*\Z', 'Use letters, digits, dots, slashes or hyphens for a shop code.')])
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=250, blank=True)
    category = models.CharField(max_length=20, choices=[('day_food', 'Day food shop'),
        ('utility', 'Utility shop'), ('night_utility', 'Night utility shop')])
    space_type = models.CharField(max_length=20, choices=[('space', 'Space'), ('room', 'Constructed room')], default='space')
    advertised_area = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                           validators=[MinValueValidator(Decimal('0.0001'))])
    authorized_services = models.TextField(blank=True)
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    hours_exception_reference = models.CharField(max_length=250, blank=True)
    active = models.BooleanField(default=True)
    availability_confirmed_on = models.DateField(null=True, blank=True)
    availability_reference = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        constraints = [models.UniqueConstraint(Lower('code'), name='estate_shop_code_unique')]

    def __str__(self):
        return f'{self.code} — {self.name}'

    def clean(self):
        if self.pk and type(self).objects.filter(pk=self.pk).exclude(code=self.code).exists():
            if self.allotments.filter(models.Q(bills__isnull=False) | models.Q(charges__isnull=False)
                                      | models.Q(security_movements__isnull=False)).exists():
                raise ValidationError({'code': 'A shop code with financial history is protected. Correct its descriptive fields instead.'})
        if bool(self.availability_confirmed_on) != bool(self.availability_reference.strip()):
            raise ValidationError({'availability_reference': 'Record both the availability date and its reference.'})
        if self.availability_confirmed_on and self.availability_confirmed_on > timezone.localdate():
            raise ValidationError({'availability_confirmed_on': 'Availability cannot be confirmed in the future.'})
        if bool(self.opens_at) != bool(self.closes_at):
            raise ValidationError({'closes_at': 'Record both opening and closing times.'})

    @property
    def occupancy_status(self):
        if self.pk:
            terms = list(self.allotments.select_related('renewal_of', 'renewal_of__renewal_of'))
            periods = Allotment.possession_periods(terms)
            if any(end is None for _, end in periods.values()):
                return 'occupied'
            if periods:
                return 'vacant'
        return 'vacant' if self.availability_confirmed_on else 'unknown'

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)


class Allotment(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='allotments')
    tenant = models.ForeignKey('Tenant', on_delete=models.PROTECT, related_name='allotments', verbose_name='Allottee')
    source_notice = models.CharField(max_length=100)
    award_reference = models.CharField(max_length=250)
    letter_issued_on = models.DateField()
    start_date = models.DateField()
    end_date = models.DateField()
    actual_area = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    measurement_reference = models.CharField(max_length=250)
    approved_rate_reference = models.CharField(max_length=250, blank=True)
    exception_reference = models.CharField(max_length=250, blank=True)
    notes = models.TextField(blank=True)
    termination_date = models.DateField(null=True, blank=True)
    termination_reference = models.CharField(max_length=250, blank=True)
    renewal_of = models.OneToOneField('self', on_delete=models.PROTECT, related_name='renewal', null=True, blank=True)
    performance_reference = models.CharField(max_length=250, blank=True)
    approval_reference = models.CharField(max_length=250, blank=True)
    possession_date = models.DateField(null=True, blank=True)
    possession_reference = models.CharField(max_length=250, blank=True)
    handover_date = models.DateField(null=True, blank=True)
    handover_reference = models.CharField(max_length=250, blank=True)
    vacation_deadline = models.DateField(null=True, blank=True)
    vacation_reference = models.CharField(max_length=250, blank=True)
    security_initial_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    security_required_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    security_due_date = models.DateField(null=True, blank=True, editable=False)
    security_requirement_reference = models.CharField(max_length=250, blank=True)
    security_requirement_reason = models.TextField(blank=True)
    security_extended_due_date = models.DateField(null=True, blank=True)
    security_extension_reference = models.CharField(max_length=250, blank=True)
    refund_review_status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending review'), ('cleared', 'Clearance reviewed'), ('exception', 'Authorized exception')])
    refund_review_reference = models.CharField(max_length=250, blank=True)
    refund_review_reason = models.TextField(blank=True)
    security_last_operation_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['shop__code', '-start_date', '-pk']
        constraints = [
            models.CheckConstraint(check=models.Q(end_date__gte=models.F('start_date')), name='estate_term_date_order'),
            models.CheckConstraint(check=models.Q(actual_area__gt=0), name='estate_term_positive_area'),
            models.UniqueConstraint(fields=['shop', 'award_reference'], condition=models.Q(renewal_of__isnull=True),
                                    name='estate_original_award_reference'),
        ]

    def __str__(self):
        return f'{self.shop.code} — {self.tenant.name} ({self.start_date} to {self.end_date})'

    def _lineage(self):
        current, seen, chain = self, set(), []
        while current is not None:
            identity = current.pk if current.pk is not None else id(current)
            if identity in seen:
                raise ValidationError({'renewal_of': 'A renewal chain cannot contain a cycle.'})
            seen.add(identity)
            chain.append(current)
            current = current.renewal_of if current.renewal_of_id else None
        return chain

    @property
    def original_award(self):
        return self._lineage()[-1]

    @property
    def notice_governed(self):
        return self.original_award.source_notice in ('368/2025', '369/2025', 'NITJSR/PDD/368/2025', 'NITJSR/PDD/369/2025')

    @property
    def extension_number(self):
        return len(self._lineage()) - 1

    @property
    def effective_end(self):
        return min(self.end_date, self.termination_date) if self.termination_date else self.end_date

    @property
    def possession_origin(self):
        term = self
        for previous in self._lineage()[1:]:
            if term.possession_date or not term.approval_reference or previous.handover_date:
                break
            if term.start_date - previous.effective_end != dt.timedelta(days=1):
                break
            term = previous
        return term if term.possession_date else None

    @staticmethod
    def possession_periods(terms):
        periods = {}
        for term in sorted(terms, key=lambda item: item.start_date):
            origin = term.possession_origin
            if origin is not None:
                periods[origin.pk] = (origin.possession_date, term.handover_date)
        return periods

    @property
    def vacation_due_date(self):
        return self.vacation_deadline or calendar_months(self.effective_end, 1)

    @property
    def security_held(self):
        root = self.original_award
        return sum((movement.amount if movement.kind == 'received' else -movement.amount
                    for movement in root.security_movements.all()), Decimal('0'))

    @property
    def security_effective_due_date(self):
        root = self.original_award
        return root.security_extended_due_date or root.security_due_date

    @property
    def security_refund_review_due(self):
        term = self.original_award
        while getattr(term, 'renewal', None):
            term = term.renewal
        return calendar_months(term.effective_end, 3)

    def status_on(self, day):
        if day < self.start_date:
            return 'future'
        if day <= self.effective_end:
            return 'current'
        return 'terminated' if self.termination_date else 'expired'

    @property
    def status(self):
        return self.status_on(timezone.localdate())

    def clean(self):
        if not all([self.shop_id, self.tenant_id, self.start_date, self.end_date, self.letter_issued_on]):
            return
        shop = Shop.objects.filter(pk=self.shop_id).first()
        if shop is None:
            return  # Foreign-key field validation supplies the missing reference error.
        if self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date must be on or after the start date.'})
        if self.start_date < self.letter_issued_on and not self.exception_reference.strip():
            raise ValidationError({'exception_reference': 'An earlier start requires the approved exception reference.'})
        if self.termination_date and not self.start_date <= self.termination_date <= self.end_date:
            raise ValidationError({'termination_date': 'Termination must be within the contractual term.'})
        for field, reference in [('termination_date', 'termination_reference'), ('possession_date', 'possession_reference'),
                                 ('handover_date', 'handover_reference'), ('vacation_deadline', 'vacation_reference')]:
            if bool(getattr(self, field)) != bool(getattr(self, reference).strip()):
                raise ValidationError({reference: 'Record both the date and its evidence/reference.'})
        if self.possession_date and (self.possession_date > timezone.localdate()
                                    or not self.start_date <= self.possession_date <= self.effective_end):
            raise ValidationError({'possession_date': 'Initial possession must fall within the effective term and cannot be in the future.'})
        if self.handover_date:
            origin = self.possession_origin
            if origin is None or not max(self.start_date, origin.possession_date) <= self.handover_date <= timezone.localdate():
                raise ValidationError({'handover_date': 'Handover requires recorded or continued possession in this term and cannot be in the future.'})
        existing = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        from ..estate.security import validate_security_requirement
        validate_security_requirement(self, existing)
        if existing and self.security_movements.exists() and (existing.shop_id, existing.tenant_id) != (self.shop_id, self.tenant_id):
            raise ValidationError('An award with security history cannot be moved to another shop or allottee.')
        if existing and self.security_movements.filter(effective_date__lt=self.letter_issued_on).exists():
            raise ValidationError('The original letter cannot follow an existing security receipt or movement.')
        if existing and existing.renewal_of_id != self.renewal_of_id:
            raise ValidationError({'renewal_of': 'Recorded renewal lineage cannot be changed; retain the original award and fee history.'})
        descendants = []
        if existing:
            descendant = type(self).objects.filter(renewal_of_id=existing.pk).first()
            while descendant:
                descendants.append(descendant)
                descendant = type(self).objects.filter(renewal_of_id=descendant.pk).first()
        if existing and descendants and (existing.shop_id, existing.tenant_id) != (self.shop_id, self.tenant_id):
            raise ValidationError('An award with recorded extensions cannot be moved to another shop or allottee.')
        if existing and not existing.renewal_of_id and self.source_notice != existing.source_notice:
            has_notice_bill = any(term.bills.filter(billing_policy='notices_368_369').exists()
                                  for term in [existing, *descendants])
            if descendants or has_notice_bill:
                raise ValidationError({'source_notice': 'The original notice is retained once extensions or notice invoices exist.'})
        if existing and self.charges.exists() and (existing.shop_id,existing.tenant_id) != (self.shop_id,self.tenant_id):
            raise ValidationError('An allotment with assessed charges cannot be moved to another shop or allottee.')
        if existing and self.bills.exists():
            if existing.shop_id != self.shop_id or existing.tenant_id != self.tenant_id:
                raise ValidationError('A billed allotment cannot be moved to another shop or allottee.')
            for bill in self.bills.all():
                first = dt.date(bill.year, bill.month, 1)
                last = first.replace(day=calendar.monthrange(bill.year, bill.month)[1])
                if self.start_date > last or self.effective_end < first:
                    raise ValidationError('The edited term would exclude an existing bill period.')
        if not shop.active and (existing is None or existing.shop_id != self.shop_id) and self.effective_end >= timezone.localdate():
            raise ValidationError({'shop': 'A retired shop cannot receive a current or future allotment.'})
        if self.renewal_of_id:
            chain = self._lineage()
            previous = chain[1]
            if len(chain) > 3:
                raise ValidationError({'renewal_of': 'Only two yearly extensions are permitted under the original award.'})
            if previous.shop_id != self.shop_id or previous.tenant_id != self.tenant_id:
                raise ValidationError({'renewal_of': 'A renewal must retain the shop and allottee.'})
            if self.start_date <= previous.effective_end:
                raise ValidationError({'start_date': 'A renewal must start after its preceding term ends.'})
            if not self.performance_reference.strip() or not self.approval_reference.strip():
                raise ValidationError({'approval_reference': 'Renewal requires satisfactory performance and approval references.'})
            if previous.notice_governed and (existing is None or existing.renewal_of_id != self.renewal_of_id
                                             or existing.approval_reference != self.approval_reference):
                fee = previous.charges.filter(kind='extension_fee').first()
                if fee is None or fee.balance_due > 0:
                    raise ValidationError({'approval_reference': 'Assess and settle the notified extension fee before approving renewal.'})
            maximum = yearly_end(self.start_date)
            if self.end_date > maximum and not self.exception_reference.strip():
                raise ValidationError({'end_date': 'A yearly extension cannot exceed one year without an approved exception.'})
        elif self.end_date > yearly_end(self.letter_issued_on) and not self.exception_reference.strip():
            raise ValidationError({'end_date': 'An initial award exceeding one year requires an approved exception.'})
        peers = type(self).objects.filter(shop_id=self.shop_id).exclude(pk=self.pk)
        if self.possession_date and not (existing and existing.possession_date):
            initially_available = shop.availability_confirmed_on and shop.availability_confirmed_on <= self.possession_date
            handed_over = peers.filter(handover_date__lt=self.possession_date).exists()
            if not initially_available and not handed_over:
                raise ValidationError({'possession_date': 'Confirm initial availability or the previous handover before possession.'})
        for peer in peers:
            if peer.start_date <= self.effective_end and peer.effective_end >= self.start_date:
                raise ValidationError({'start_date': 'This shop already has an overlapping allotment.'})
        terms = [*peers, self]
        by_id = {term.pk: term for term in terms if term.pk}
        for term in terms:
            if term.renewal_of_id in by_id:
                term.renewal_of = by_id[term.renewal_of_id]
            if term.handover_date and term.possession_origin is None:
                raise ValidationError({'handover_date': 'Keep the possession evidence supporting the recorded handover.'})
        periods = sorted(self.possession_periods(terms).values(), key=lambda period: period[0])
        for (_, end), (start, _) in zip(periods, periods[1:]):
            if end is None or start <= end:
                raise ValidationError({'possession_date': 'Previous physical possession must end before a new possession begins.'})

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        created = self._state.adding
        with transaction.atomic(using=using):
            # Acquire the SQLite write reservation before overlap reads, including an empty shop.
            Shop.objects.using(using).filter(pk=self.shop_id).update(active=models.F('active'))
            self.full_clean()
            result = super().save(*args, **kwargs)
            if created and not self.renewal_of_id and self.source_notice in (
                    '368/2025', '369/2025', 'NITJSR/PDD/368/2025', 'NITJSR/PDD/369/2025'):
                self.seed_requirements()
            if self.renewal_of_id:
                fee = self.renewal_of.charges.filter(kind='extension_fee').first()
                if fee and fee.renewal_term_id is None:
                    fee.renewal_term = self
                    fee.save(update_fields=['renewal_term','updated_at'])
            return result

    def seed_requirements(self):
        for kind, due, applicable, reason in [
            ('police', self.letter_issued_on + dt.timedelta(days=30), True, ''),
            ('gst', self.letter_issued_on + dt.timedelta(days=90), not bool(self.tenant.gstin), 'GST already recorded'),
            ('food', None, self.shop.category in ('day_food', 'night_utility'), 'Non-food utility activity'),
        ]:
            self.requirements.get_or_create(kind=kind, defaults={'due_date': due, 'applicable': applicable,
                'not_applicable_reason': '' if applicable else reason})


class AllotmentRequirement(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    allotment = models.ForeignKey(Allotment, on_delete=models.PROTECT, related_name='requirements')
    kind = models.CharField(max_length=20, choices=[('police', 'Police verification'), ('gst', 'GST registration'),
        ('food', 'Food licence'), ('performance', 'Performance review'), ('other', 'Other condition')])
    applicable = models.BooleanField(default=True)
    not_applicable_reason = models.CharField(max_length=500, blank=True)
    due_date = models.DateField(null=True, blank=True)
    submitted_on = models.DateField(null=True, blank=True)
    submission_reference = models.CharField(max_length=250, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    unresolved_issue = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'pk']

    @property
    def status(self):
        if not self.applicable:
            return 'not_applicable'
        if self.unresolved_issue:
            return 'issue'
        if self.verified_on:
            return 'verified'
        if self.due_date and self.due_date < timezone.localdate():
            return 'overdue'
        return 'submitted' if self.submitted_on else 'pending'

    def clean(self):
        if not self.applicable and not self.not_applicable_reason.strip():
            raise ValidationError({'not_applicable_reason': 'Explain why this condition does not apply.'})
        if bool(self.submitted_on) != bool(self.submission_reference.strip()):
            raise ValidationError({'submission_reference': 'Record submission date and reference together.'})
        if bool(self.verified_on) != bool(self.verified_by_id):
            raise ValidationError({'verified_on': 'Verification requires a date and the verifying user.'})
        if self.verified_on and (not self.submitted_on or self.verified_on < self.submitted_on):
            raise ValidationError({'verified_on': 'Verify only after documented submission.'})
        if any(day and day > timezone.localdate() for day in (self.submitted_on, self.verified_on)):
            raise ValidationError('Submission and verification cannot be recorded in the future.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
