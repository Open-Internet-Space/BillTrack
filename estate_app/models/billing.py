from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import datetime
import re
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
    month       = models.PositiveSmallIntegerField(help_text="1=Jan, 2=Feb ... 12=Dec")
    year        = models.PositiveSmallIntegerField()

    # Charges (base amounts before GST)
    rent        = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     help_text="Base rent amount (before GST)")
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
    due_date    = models.DateField()
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
        unique_together = ['tenant', 'month', 'year']
        verbose_name = 'Bill'
        verbose_name_plural = 'Bills'

    def __str__(self):
        invoice_display = self.invoice_no or f"[Pending] {self.tenant.name} {self.get_month_name()} {self.year}"
        return invoice_display

    def clean(self):
        if self.issue_date and self.issue_date > timezone.localdate():
            raise ValidationError({'issue_date': 'Confirmed receipt date cannot be in the future.'})
        if self.month < 1 or self.month > 12:
            raise ValidationError({'month': 'Month must be between 1 and 12'})
        if self.year < 2000 or self.year > 2100:
            raise ValidationError({'year': 'Please enter a valid year'})
        if self.rent < 0 or self.electric < 0 or self.water < 0:
            raise ValidationError('Charges cannot be negative')

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

    def calculate_gst(self):
        """Calculate GST on rent based on tenant settings"""
        gst_rate = self.tenant.get_gst_rate()
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
            status__in=['Unpaid', 'Partial'],
            issue_date__isnull=False,
            due_date__lt=today,
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
        if not self.issue_date or self.status == 'Paid':
            return Decimal('0')
        if self.balance_due <= 0:
            return max(Decimal('0'), self.penalty_accrued - self.penalty_paid_after_start)
        return max(Decimal('0'), self.accrued_penalty(timezone.localdate()) - self.penalty_paid_after_start)

    def accrued_penalty(self, as_of):
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
        paid = getattr(self, '_penalty_paid', None)
        if paid is not None:
            return paid
        return self.payments.filter(payment_date__gt=self.penalty_start_date).aggregate(total=models.Sum('penalty_paid'))['total'] or Decimal('0')

    def penalty_for(self, balance, as_of, penalty_config=None):
        start_date = self.penalty_start_date
        if start_date is None or balance <= 0 or as_of <= start_date:
            return Decimal('0')
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
        return self.due_date if self.issue_date else None

    @property
    def receipt_status(self):
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

        if paid <= 0:
            self.status = 'Unpaid'
        elif paid >= total and penalty_due <= 0:
            self.status = 'Paid'
        else:
            self.status = 'Partial'

        self.save(update_fields=['status', 'penalty_accrued', 'penalty_accrued_on'])

    @transaction.atomic
    def save(self, *args, **kwargs):
        previous = Bill.objects.filter(pk=self.pk).values('issue_date', 'due_date').first() if self.pk else None
        if previous and kwargs.get('update_fields') is not None and 'issue_date' not in kwargs['update_fields']:
            self.issue_date = previous['issue_date']
        if self.issue_date and self.issue_date > timezone.localdate():
            raise ValidationError({'issue_date': 'Confirmed receipt date cannot be in the future.'})
        receipt_changed = previous is not None and previous['issue_date'] != self.issue_date
        if self.issue_date:
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

        if not self.due_date:
            base_date = self.issue_date or timezone.localdate()
            self.due_date = base_date + datetime.timedelta(days=5)

        # Calculate and store GST before saving
        gst_total, cgst, sgst, igst = self.calculate_gst()
        self.gst_on_rent = gst_total
        self.cgst_on_rent = cgst
        self.sgst_on_rent = sgst
        self.igst_on_rent = igst

        super().save(*args, **kwargs)

        if receipt_changed:
            self.__dict__.pop('_penalty_paid', None)
            self.update_status()
