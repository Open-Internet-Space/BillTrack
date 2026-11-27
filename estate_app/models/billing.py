from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
import datetime
import calendar
import re
from zoneinfo import ZoneInfo
from .allottees import Tenant


class Bill(models.Model):
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Partial', 'Partial'),
        ('Paid', 'Paid'),
    ]
    GST_TREATMENT_CHOICES = [
        ('cgst_sgst', 'CGST + SGST'),
        ('igst', 'IGST'),
    ]

    # Invoice Info - internal reference (Format: Month/Year/Autonumber)
    invoice_no  = models.CharField(max_length=100, unique=True, blank=True, null=True,
                                   help_text="Auto format: Month/Year/Autonumber, e.g. May/2026/001")
    tenant      = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='bills', verbose_name='Allottee')
    allotment = models.ForeignKey('Allotment', on_delete=models.PROTECT, related_name='bills', null=True, blank=True)
    billing_category = models.CharField(max_length=20, default='legacy', choices=[
        ('allotment', 'Allotment'), ('other', 'Other monthly charges'), ('legacy', 'Legacy unassigned')])
    billing_policy = models.CharField(max_length=20, default='legacy_receipt', choices=[
        ('legacy_receipt', 'Legacy confirmed receipt'), ('notices_368_369', 'Notices 368–369')])
    raised_date = models.DateField(null=True, blank=True)
    email_dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatch_recipient = models.EmailField(blank=True)
    dispatch_message_reference = models.CharField(max_length=250, blank=True)
    dispatch_sender = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name='estate_dispatched_bills')
    rent_revision = models.ForeignKey('RentRevision', on_delete=models.PROTECT, null=True, blank=True, related_name='bills')
    rate_snapshot = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, editable=False)
    area_snapshot = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, editable=False)
    rent_revision_reference = models.CharField(max_length=250, blank=True, editable=False)
    rent_override_reason = models.TextField(blank=True)
    rate_exception_reference = models.CharField(max_length=250, blank=True)
    month       = models.PositiveSmallIntegerField(help_text="1=Jan, 2=Feb ... 12=Dec")
    year        = models.PositiveSmallIntegerField()

    # Charges (base amounts before GST)
    rent        = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     help_text="Base rent amount (before GST)")
    full_month_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Original full-month rent before any holiday waiver. Leave empty only for legacy records.')
    holiday_start_date = models.DateField(null=True, blank=True)
    holiday_end_date = models.DateField(null=True, blank=True)
    holiday_closed_days = models.PositiveSmallIntegerField(default=0, editable=False)
    holiday_waiver = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    electric    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    electric_reading = models.CharField(max_length=100, blank=True,
                                        help_text="Electricity reading / units details for invoice display")
    water       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_treatment = models.CharField(max_length=20, choices=GST_TREATMENT_CHOICES, default='cgst_sgst',
                                     help_text="Choose CGST+SGST or IGST for this bill")

    # GST (calculated automatically based on tenant/system settings)
    gst_on_rent     = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False,
                                         help_text="Total GST on rent (auto-calculated)")
    cgst_on_rent    = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False,
                                         help_text="CGST component (auto-calculated)")
    sgst_on_rent    = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False,
                                         help_text="SGST component (auto-calculated)")
    igst_on_rent    = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False,
                                         help_text="IGST component (auto-calculated)")

    # Dates
    due_date    = models.DateField(null=True, blank=True)
    issue_date  = models.DateField(null=True, blank=True, help_text="Confirmed receipt date through mail; payment is due five calendar days later")
    dispatch_ref_no = models.CharField(max_length=100, blank=True, help_text="Dispatch / reference number after signature")
    receipt_reset_snapshot = models.JSONField(null=True, blank=True, editable=False,
                                              help_text="Original receipt dates and penalties retained for recovery where available")

    # Status (calculated by backend)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Unpaid', editable=False)
    penalty_accrued = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    penalty_accrued_on = models.DateField(null=True, blank=True, editable=False)

    # Metadata
    notes       = models.TextField(blank=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bills_created')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month', 'tenant__name']
        constraints = [
            models.UniqueConstraint(fields=['allotment', 'month', 'year'], condition=models.Q(allotment__isnull=False),
                                    name='bill_allotment_period_unique'),
            models.UniqueConstraint(fields=['tenant', 'month', 'year'], condition=models.Q(allotment__isnull=True),
                                    name='bill_unassigned_period_unique'),
            models.CheckConstraint(check=(models.Q(billing_category='allotment', allotment__isnull=False)
                | models.Q(billing_category__in=['other', 'legacy'], allotment__isnull=True)), name='bill_category_link_consistent'),
            models.CheckConstraint(check=(models.Q(billing_policy='legacy_receipt')
                | models.Q(billing_policy='notices_368_369', allotment__isnull=False, billing_category='allotment')),
                name='bill_policy_link_consistent'),
            models.CheckConstraint(check=(models.Q(email_dispatched_at__isnull=True)
                | (models.Q(billing_policy='notices_368_369', raised_date__isnull=False, dispatch_sender__isnull=False)
                   & ~models.Q(dispatch_recipient='') & ~models.Q(dispatch_message_reference=''))),
                name='bill_confirmed_dispatch_evidence'),
        ]
        verbose_name = 'Bill'
        verbose_name_plural = 'Bills'

    def __str__(self):
        invoice_display = self.invoice_no or f"[Pending] {self.tenant.name} {self.get_month_name()} {self.year}"
        return invoice_display

    def clean(self, *, allotment=None, check_retained_payments=True):
        if self.billing_policy == 'notices_368_369':
            if not self.allotment_id or not self.allotment.notice_governed:
                raise ValidationError({'billing_policy': 'This policy requires an allotment governed by Notices 368–369.'})
            if self.issue_date:
                raise ValidationError({'issue_date': 'Keep legacy receipt date empty; record notice email dispatch separately.'})
            if self.raised_date and self.raised_date > timezone.localdate():
                raise ValidationError({'raised_date': 'A finalized invoice cannot have a future raised date.'})
            if check_retained_payments and self.pk:
                retained = self.payments.all()
                if self.raised_date:
                    retained = retained.filter(payment_date__lt=self.raised_date)
                if retained.exists():
                    raise ValidationError({'raised_date': 'Keep the invoice raised on or before its earliest retained payment.'})
            if self.email_dispatched_at:
                if timezone.is_naive(self.email_dispatched_at) or self.email_dispatched_at > timezone.now():
                    raise ValidationError({'email_dispatched_at': 'Record a confirmed, timezone-aware dispatch timestamp, not a future time.'})
                if not self.raised_date or self.dispatch_day < self.raised_date:
                    raise ValidationError({'email_dispatched_at': 'Raise the invoice before recording confirmed dispatch.'})
                if not self.dispatch_recipient.strip() or not self.dispatch_message_reference.strip() or not self.dispatch_sender_id:
                    raise ValidationError('Confirmed dispatch requires recipient, message reference and the sending staff member.')
        elif self.raised_date or self.email_dispatched_at or self.dispatch_recipient or self.dispatch_message_reference or self.dispatch_sender_id:
            raise ValidationError({'billing_policy': 'Notice date/evidence fields cannot be used on legacy receipt-policy bills.'})
        if self.issue_date and self.issue_date > timezone.localdate():
            raise ValidationError({'issue_date': 'Confirmed receipt date cannot be in the future.'})
        if not isinstance(self.month, int) or not 1 <= self.month <= 12:
            raise ValidationError({'month': 'Month must be between 1 and 12'})
        if not isinstance(self.year, int) or not 2000 <= self.year <= 2100:
            raise ValidationError({'year': 'Please enter a valid year'})
        if self.rent < 0 or self.electric < 0 or self.water < 0:
            raise ValidationError('Charges cannot be negative')
        if self.full_month_rent is None and (self.holiday_start_date or self.holiday_end_date):
            raise ValidationError({'full_month_rent': 'Record the full-month rent before applying a holiday waiver.'})
        if self.full_month_rent is not None:
            from ..estate.billing import holiday_rent
            holiday_rent(self.full_month_rent, self.year, self.month, self.holiday_start_date, self.holiday_end_date)
        if (self.billing_category == 'allotment') != bool(self.allotment_id):
            raise ValidationError({'allotment': 'Allotment billing requires a term; other/legacy billing cannot have one.'})
        if self.allotment_id:
            from .estate import Allotment
            term = allotment if allotment is not None else Allotment.objects.filter(pk=self.allotment_id).first()
            if term is None or term.tenant_id != self.tenant_id:
                raise ValidationError({'allotment': 'The selected term must belong to this allottee.'})
            first = datetime.date(self.year, self.month, 1)
            last = first.replace(day=calendar.monthrange(self.year, self.month)[1])
            if term.start_date > last or term.effective_end < first:
                raise ValidationError({'month': 'This billing month falls outside the selected allotment term.'})

    def prepare_notice_rent(self, refresh=False):
        if self.billing_policy != 'notices_368_369' or not self.allotment_id:
            return
        from ..estate.billing import annual_revisions, rent_schedule
        flat = self.allotment.rent_basis == 'flat'
        if refresh or self.rate_snapshot is None or (not flat and self.area_snapshot is None):
            try:
                schedule = rent_schedule(self.allotment, self.year, self.month)
            except ValidationError:
                if self.full_month_rent is None or not self.rent_override_reason.strip():
                    raise
                if self.raised_date and not self.rate_exception_reference.strip():
                    raise ValidationError({'rate_exception_reference': 'Record approved authority before issuing without a rate schedule.'})
                return
            self.rent_revision_id = schedule['revision_id']
            self.rate_snapshot, self.area_snapshot = schedule['rate'], schedule['area']
            self.rent_revision_reference = schedule['approval_reference']
        expected = (self.rate_snapshot if flat else self.rate_snapshot * self.area_snapshot).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if self.full_month_rent is None:
            self.full_month_rent = expected
        if self.full_month_rent != expected and not self.rent_override_reason.strip():
            raise ValidationError({'rent_override_reason': 'Explain the reviewed difference from the approved full-month charge.'})
        if self.rent_revision_id:
            if self.rent_revision.original_award_id != self.allotment.original_award.pk:
                raise ValidationError({'rent_revision': 'The rate must belong to this original award.'})
            through = datetime.date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])
            missing = annual_revisions(self.rate_snapshot, self.rent_revision.effective_date, through, flat=flat)
            if self.raised_date and missing and not self.rate_exception_reference.strip():
                raise ValidationError({'rate_exception_reference': 'Approve the missing April revision before final issue, or record its authorized exception.'})

    # ── Business Logic (ALL calculations done by backend) ─────────────────────

    def get_month_name(self):
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return months[self.month] if 1 <= self.month <= 12 else str(self.month)

    def generate_invoice_no(self):
        """
        Generate the next internal reference for this bill's accounting month.
        Numbering is shared across tenants in a month.
        """
        # Serial is generated month-wise across all units:
        # e.g., May/001, May/002
        prefix = f"{self.get_month_name()}/{self.year}/"
        existing_numbers = Bill.objects.filter(
            year=self.year,
            month=self.month,
            invoice_no__startswith=prefix,
        )
        if self.pk:
            existing_numbers = existing_numbers.exclude(pk=self.pk)

        max_serial = 0
        serial_pattern = re.compile(r'/(\d+)$')
        for invoice_no in existing_numbers.values_list('invoice_no', flat=True):
            match = serial_pattern.search(invoice_no or '')
            if match:
                max_serial = max(max_serial, int(match.group(1)))

        return f"{prefix}{max_serial + 1:03d}"

    def calculate_gst(self, system_settings=None):
        """Calculate GST on rent based on tenant settings"""
        gst_rate = self.tenant.get_gst_rate(system_settings)
        if gst_rate > 0:
            total_gst = round(self.rent * gst_rate / 100, 2)
            if self.gst_treatment == 'igst':
                return total_gst, Decimal('0'), Decimal('0'), total_gst
            cgst = round(total_gst / 2, 2)
            sgst = total_gst - cgst  # Ensure they add up exactly
            return total_gst, cgst, sgst, Decimal('0')
        return Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0')

    @property
    def rent_with_gst(self):
        """Rent including GST"""
        return self.rent + self.gst_on_rent

    @property
    def total_amount(self):
        """Total bill amount including GST"""
        return self.rent + self.gst_on_rent + self.electric + self.water

    @property
    def amount_paid(self):
        """Total paid so far (sum of all payments)"""
        if hasattr(self, '_amount_paid'):
            return self._amount_paid or Decimal('0')
        return sum(p.amount for p in self.payments.all())

    @property
    def amount_paid_including_penalty(self):
        """Total received, including any payment allocated to penalty."""
        return sum((p.amount + p.penalty_paid for p in self.payments.all()), Decimal('0'))

    @property
    def balance_due(self):
        """Outstanding amount (backend calculates)"""
        return max(Decimal('0'), self.total_amount - self.amount_paid)

    def previous_due_bills(self):
        """
        Older bills for the same tenant that are still pending after due date.
        These are used as arrears on the current invoice without storing a
        duplicate amount on the bill itself.
        """
        # "Previous dues" is intentionally dynamic at read time. We do not
        # denormalize/copy arrears into the current bill to avoid drift.
        today = timezone.localdate()
        return Bill.objects.filter(
            tenant=self.tenant,
            allotment_id=self.allotment_id,
            status__in=['Unpaid', 'Partial'],
            due_date__lt=today,
        ).filter(
            models.Q(billing_policy='legacy_receipt', issue_date__isnull=False)
            | models.Q(billing_policy='notices_368_369', raised_date__isnull=False)
        ).filter(
            models.Q(year__lt=self.year) |
            models.Q(year=self.year, month__lt=self.month)
        ).exclude(pk=self.pk)

    @property
    def previous_balance(self):
        """Outstanding principal from older overdue bills for this tenant."""
        return sum((bill.balance_due for bill in self.previous_due_bills()), Decimal('0'))

    @property
    def previous_penalty(self):
        """Penalty already accrued on older overdue bills for this tenant."""
        return sum((bill.penalty for bill in self.previous_due_bills()), Decimal('0'))

    @property
    def penalty(self):
        """
        Calculate penalty based on tenant-specific or system settings.
        Supports: percentage per annum, lumpsum, or none
        """
        if self.penalty_start_date is None or self.status == 'Paid':
            return Decimal('0')
        if self.balance_due <= 0:
            return max(Decimal('0'), self.penalty_accrued - self.penalty_paid_after_start)
        return max(Decimal('0'), self.accrued_penalty(timezone.localdate()) - self.penalty_paid_after_start)

    def accrued_penalty(self, as_of):
        if self.billing_policy == 'notices_368_369':
            from ..estate.billing import notice_interest
            return notice_interest(self.total_amount, self.penalty_start_date, as_of,
                                   [(p.payment_date, p.amount) for p in self.payments.all()])
        start = self.penalty_start_date
        if start is None:
            return Decimal('0')
        balance = self.total_amount
        accrued = Decimal('0')
        previous_date = start
        config = getattr(self, '_penalty_config', None) or self.tenant.get_penalty_config()
        for payment in sorted(self.payments.all(), key=lambda item: (item.payment_date, item.pk or 0)):
            if payment.payment_date > as_of:
                break
            if payment.payment_date > previous_date and balance > 0:
                accrued += self.penalty_for(balance, payment.payment_date, config) - self.penalty_for(balance, previous_date, config)
                previous_date = payment.payment_date
            balance = max(Decimal('0'), balance - payment.amount)
        if as_of > previous_date and balance > 0:
            accrued += self.penalty_for(balance, as_of, config) - self.penalty_for(balance, previous_date, config)
        return accrued

    @property
    def penalty_paid_after_start(self):
        if self.penalty_start_date is None:
            return Decimal('0')
        if self.billing_policy == 'notices_368_369':
            return sum((p.penalty_paid for p in self.payments.all()), Decimal('0'))
        paid = getattr(self, '_penalty_paid', None)
        if paid is not None:
            return paid
        return self.payments.filter(payment_date__gt=self.penalty_start_date).aggregate(total=models.Sum('penalty_paid'))['total'] or Decimal('0')

    def penalty_for(self, balance, as_of, penalty_config=None):
        start_date = self.penalty_start_date
        if start_date is None or balance <= 0 or as_of <= start_date:
            return Decimal('0')
        if self.billing_policy == 'notices_368_369':
            from ..estate.billing import notice_interest
            return notice_interest(balance, start_date, as_of, [])
        days_overdue = (as_of - start_date).days
        penalty_config = penalty_config or self.tenant.get_penalty_config()

        if penalty_config['type'] == 'none':
            return Decimal('0')

        if penalty_config['type'] == 'percentage':
            rate = penalty_config['rate'] / 100  # Convert % to decimal
            if penalty_config['frequency'] == 'day':
                penalty_amount = balance * rate * days_overdue
            elif penalty_config['frequency'] == 'month':
                penalty_amount = balance * rate * days_overdue / 30
            else:
                penalty_amount = balance * rate * days_overdue / 365
            return round(penalty_amount, 2)

        if penalty_config['type'] == 'lumpsum':
            if penalty_config['frequency'] == 'day':
                periods = days_overdue
            elif penalty_config['frequency'] == 'month':
                periods = Decimal(days_overdue) / Decimal('30')
            else:
                periods = Decimal(days_overdue) / Decimal('365')
            return round(penalty_config['lumpsum'] * periods, 2)

        return Decimal('0')

    @property
    def penalty_calculation(self):
        if self.billing_policy == 'notices_368_369':
            start = self.penalty_start_date
            return {'principal': str(self.balance_due), 'start_date': start.isoformat() if start else None,
                    'days': self.days_overdue, 'type': 'percentage', 'frequency': 'year', 'rate': '12.00',
                    'formula': '12% simple interest on dated unpaid principal segments, actual days / 365; final total rounded to two places.'
                        if start else 'Confirmed email dispatch is required before late interest accrues.',
                    'result': str(self.penalty)}
        if not self.issue_date:
            return {'principal': str(self.balance_due), 'start_date': None, 'days': 0,
                    'formula': 'Pending receipt confirmation; no late-payment penalty.', 'result': '0'}
        config = getattr(self, '_penalty_config', None) or self.tenant.get_penalty_config()
        if self.balance_due <= 0 and self.penalty_accrued:
            paid = self.penalty_paid_after_start
            return {
                'principal': '0',
                'start_date': self.penalty_start_date.isoformat(),
                'days': (self.penalty_accrued_on - self.penalty_start_date).days if self.penalty_accrued_on else 0,
                'type': config['type'],
                'frequency': config['frequency'],
                'formula': f"Penalty accrued through {self.penalty_accrued_on}; {paid} paid of {self.penalty_accrued}",
                'result': str(self.penalty),
            }
        details = {
            'principal': str(self.balance_due),
            'start_date': self.penalty_start_date.isoformat(),
            'days': self.days_overdue,
            'type': config['type'],
            'frequency': config['frequency'],
        }
        if config['type'] == 'percentage':
            divisor = {'day': 1, 'month': 30, 'year': 365}.get(config['frequency'], 365)
            details.update(rate=str(config['rate']), formula=f"{self.balance_due} × {config['rate']}% × {self.days_overdue} ÷ {divisor}")
        elif config['type'] == 'lumpsum':
            divisor = {'day': 1, 'month': 30, 'year': 365}.get(config['frequency'], 365)
            details.update(amount=str(config['lumpsum']), formula=f"{config['lumpsum']} × {self.days_overdue} ÷ {divisor}")
        else:
            details['formula'] = 'No penalty configured'
        if self.amount_paid > 0:
            details['formula'] = f"Accrued across payment dates: {self.accrued_penalty(timezone.localdate())}; penalty paid: {self.penalty_paid_after_start}"
        details['result'] = str(self.penalty)
        return details

    @property
    def total_payable(self):
        """Current balance + current penalty + older overdue dues."""
        return self.balance_due + self.penalty + self.previous_balance + self.previous_penalty

    @property
    def days_overdue(self):
        """How many penalty days have elapsed"""
        today = timezone.localdate()
        if self.penalty_start_date is None or today <= self.penalty_start_date:
            return 0
        return (today - self.penalty_start_date).days

    @property
    def penalty_start_date(self):
        """Accrue only for days after the confirmed payment deadline."""
        if self.billing_policy == 'notices_368_369':
            return max(self.due_date, self.dispatch_day) if self.due_date and self.dispatch_day else None
        return self.due_date if self.issue_date else None

    @property
    def dispatch_day(self):
        return timezone.localtime(self.email_dispatched_at, ZoneInfo('Asia/Kolkata')).date() if self.email_dispatched_at else None

    @property
    def is_draft(self):
        return self.billing_policy == 'notices_368_369' and not self.raised_date

    @property
    def confirmation_date(self):
        return self.dispatch_day if self.billing_policy == 'notices_368_369' else self.issue_date

    @property
    def deadline_established(self):
        return bool(self.due_date and (self.raised_date if self.billing_policy == 'notices_368_369' else self.issue_date))

    @property
    def payment_days_overdue(self):
        return max(0, (timezone.localdate() - self.due_date).days) if self.deadline_established and self.status != 'Paid' else 0

    @property
    def receipt_status(self):
        if self.billing_policy == 'notices_368_369':
            return 'Draft' if not self.raised_date else 'Email Dispatch Confirmed' if self.email_dispatched_at else 'Pending Email Dispatch'
        return 'Receipt Confirmed' if self.issue_date else 'Pending Receipt'

    def update_status(self):
        """
        Backend logic: Recalculate status based on payments.
        Called automatically after each payment.
        """
        paid = self.amount_paid
        total = self.total_amount
        paid_in_order = Decimal('0')
        settled_on = None
        for payment in sorted(self.payments.all(), key=lambda item: (item.payment_date, item.pk or 0)):
            paid_in_order += payment.amount
            if paid_in_order >= total:
                settled_on = payment.payment_date
                break
        self.penalty_accrued_on = settled_on
        self.penalty_accrued = self.accrued_penalty(settled_on) if settled_on else Decimal('0')
        penalty_paid = self.penalty_paid_after_start
        penalty_due = max(Decimal('0'), self.penalty_accrued - penalty_paid)

        if paid >= total and penalty_due <= 0:
            self.status = 'Paid'
        elif paid <= 0:
            self.status = 'Unpaid'
        else:
            self.status = 'Partial'

        self.save(update_fields=['status', 'penalty_accrued', 'penalty_accrued_on'])

    @transaction.atomic
    def save(self, *args, **kwargs):
        inputs = ('rent', 'electric', 'water', 'gst_treatment', 'full_month_rent',
                  'holiday_start_date', 'holiday_end_date', 'month', 'year')
        policy_inputs = ('billing_policy', 'raised_date', 'email_dispatched_at', 'dispatch_recipient',
                         'dispatch_message_reference', 'dispatch_sender_id')
        rate_inputs = ('rent_revision_id', 'rate_snapshot', 'area_snapshot', 'rent_revision_reference',
                       'rent_override_reason', 'rate_exception_reference')
        taxes = ('gst_on_rent', 'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent')
        previous = Bill.objects.filter(pk=self.pk).values('issue_date', 'due_date', *inputs, *taxes, *policy_inputs, *rate_inputs).first() if self.pk else None
        update_fields = kwargs.get('update_fields')
        if previous and update_fields is not None:
            for field in (*inputs, *policy_inputs, *rate_inputs):
                if field not in update_fields and field.removesuffix('_id') not in update_fields:
                    setattr(self, field, previous[field])
        finalizing = previous is not None and previous['raised_date'] is None and self.raised_date is not None
        period_changed = previous is not None and any(previous[key] != getattr(self, key) for key in ('year', 'month'))
        if self.billing_policy == 'notices_368_369' and (finalizing or period_changed) and not self.rent_override_reason.strip():
            self.full_month_rent = None
        self.prepare_notice_rent(refresh=previous is None or finalizing or period_changed)
        if (finalizing or period_changed) and update_fields is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | set(rate_inputs) | {'full_month_rent'}
        if self.full_month_rent is not None:
            from ..estate.billing import holiday_rent
            result = holiday_rent(self.full_month_rent, self.year, self.month, self.holiday_start_date, self.holiday_end_date)
            self.rent = result['applicable_rent']
            self.holiday_closed_days = result['closed_days']
            self.holiday_waiver = result['waiver_amount']
        elif self.holiday_start_date or self.holiday_end_date:
            raise ValidationError({'full_month_rent': 'Record the original full-month rent before applying holiday dates.'})
        money_changed = previous is None or any(previous[field] != getattr(self, field) for field in inputs)
        if previous and kwargs.get('update_fields') is not None and 'issue_date' not in kwargs['update_fields']:
            self.issue_date = previous['issue_date']
        if self.issue_date and self.issue_date > timezone.localdate():
            raise ValidationError({'issue_date': 'Confirmed receipt date cannot be in the future.'})
        receipt_changed = previous is not None and previous['issue_date'] != self.issue_date
        policy_changed = previous is not None and any(previous[field] != getattr(self, field) for field in policy_inputs)
        if self.billing_policy == 'notices_368_369':
            self.due_date = self.raised_date + datetime.timedelta(days=7) if self.raised_date else None
            if update_fields is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'due_date'}
        elif self.issue_date:
            # Preserve earlier confirmed deadlines on unrelated edits.
            self.due_date = (self.issue_date + datetime.timedelta(days=5)
                             if previous is None or receipt_changed else previous['due_date'])
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'due_date'}
        # Keep "derived fields" deterministic during every save.
        # invoice_no and GST splits are backend-owned and never trusted from UI.
        if not self.invoice_no:
            self.invoice_no = self.generate_invoice_no()
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'invoice_no'}

        if not self.due_date and self.billing_policy == 'legacy_receipt':
            base_date = self.issue_date or timezone.localdate()
            self.due_date = base_date + datetime.timedelta(days=5)

        self.clean()
        if money_changed:
            gst_total, cgst, sgst, igst = self.calculate_gst()
            self.gst_on_rent, self.cgst_on_rent, self.sgst_on_rent, self.igst_on_rent = gst_total, cgst, sgst, igst
        else:
            for field in taxes:
                setattr(self, field, previous[field])
        if update_fields is not None and money_changed:
            kwargs['update_fields'] = set(kwargs['update_fields']) | set(taxes) | {
                'rent', 'holiday_closed_days', 'holiday_waiver'}

        super().save(*args, **kwargs)

        if receipt_changed or money_changed or policy_changed:
            self.__dict__.pop('_penalty_paid', None)
            self.update_status()
