from django.db import models
from django.core.validators import RegexValidator
from decimal import Decimal
import datetime
import uuid
from .settings import SystemSettings


class Tenant(models.Model):
    PENALTY_TYPE_CHOICES = [
        ('system', 'Use System Default'),
        ('percentage', 'Percentage (% per annum)'),
        ('lumpsum', 'Lumpsum (fixed amount)'),
        ('none', 'No Penalty'),
    ]
    PENALTY_FREQUENCY_CHOICES = [
        ('system', 'Use System Default'),
        ('day', 'Per Day'),
        ('month', 'Per Month'),
        ('year', 'Per Year'),
    ]

    # Basic Info
    uuid       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name       = models.CharField(max_length=200, help_text="Allottee/Business name")
    allotment_description = models.CharField(max_length=200, blank=True, default='', validators=[RegexValidator(r'\A[^\r\n]*\Z', 'Use one line for the allotment description.')], help_text='Optional identifier, for example Shop 12, Market Block. Shown beside the name in lists and selectors.')
    type       = models.CharField(max_length=50)
    contact    = models.CharField(max_length=20, blank=True)
    contact_not_provided = models.BooleanField(default=False, verbose_name='Contact: Not Provided')
    email      = models.EmailField(blank=True)
    email_not_provided = models.BooleanField(default=False, verbose_name='Email: Not Provided')
    gstin      = models.CharField(max_length=15, blank=True, help_text="GSTIN for invoice display")
    gstin_not_provided = models.BooleanField(default=False, verbose_name='GSTIN: Not Provided')
    address    = models.TextField(blank=True)
    address_not_provided = models.BooleanField(default=False, verbose_name='Address: Not Provided')
    active     = models.BooleanField(default=True)
    due_days   = models.PositiveSmallIntegerField(default=5, help_text="Default due days after issue/signature date")

    # GST Configuration (Tenant-specific)
    gst_applicable = models.BooleanField(default=True, help_text="Apply GST to this allottee's rent")
    custom_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                         help_text="Custom GST rate % (leave blank to use system default)")

    # Penalty Configuration (Tenant-specific)
    penalty_type = models.CharField(max_length=20, choices=PENALTY_TYPE_CHOICES, default='system',
                                    help_text="Penalty calculation method for this allottee")
    custom_penalty_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                             help_text="Custom penalty % per annum (if percentage type)")
    custom_penalty_lumpsum = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                 help_text="Custom fixed penalty amount (if lumpsum type)")
    custom_penalty_frequency = models.CharField(max_length=10, choices=PENALTY_FREQUENCY_CHOICES, default='system',
                                                help_text="Custom penalty frequency")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Allottee'
        verbose_name_plural = 'Allottees'

    @property
    def display_name(self):
        return f"{self.name} — {self.allotment_description}" if self.allotment_description else self.name

    def __str__(self):
        return self.display_name

    @classmethod
    def with_last_billed_month(cls, queryset=None):
        from .billing import Bill

        latest = Bill.objects.filter(tenant_id=models.OuterRef('pk')).order_by('-year', '-month')
        return (queryset if queryset is not None else cls.objects.all()).annotate(_last_billed_period=models.Subquery(
            latest.annotate(period=models.F('year') * 100 + models.F('month')).values('period')[:1]))

    @property
    def last_billed_month(self):
        if '_last_billed_period' in self.__dict__:
            period = self._last_billed_period
        else:
            period = type(self).with_last_billed_month().filter(pk=self.pk).values_list('_last_billed_period', flat=True).first()
        if period is None:
            return 'Never billed'
        return datetime.date(period // 100, period % 100, 1).strftime('%B %Y')

    def save(self, *args, **kwargs):
        for field in ('contact', 'email', 'gstin', 'address'):
            if getattr(self, f'{field}_not_provided'):
                setattr(self, field, '')
        self.gstin = (self.gstin or '').strip().upper()
        self.email = (self.email or '').strip()
        return super().save(*args, **kwargs)

    def get_gst_rate(self, system_settings=None):
        """Get effective GST rate for this tenant"""
        if not self.gst_applicable:
            return Decimal('0')
        if self.custom_gst_rate is not None:
            return Decimal(str(self.custom_gst_rate))
        settings = system_settings if system_settings is not None else SystemSettings.get_settings()
        return Decimal(str(settings.gst_rate)) if settings.gst_applicable else Decimal('0')

    def get_penalty_config(self, system_settings=None):
        """Get effective penalty configuration for this tenant"""
        # Resolution order:
        # 1) Tenant explicit "none"
        # 2) Tenant explicit percentage/lumpsum values
        # 3) System defaults
        settings = system_settings if system_settings is not None else SystemSettings.get_settings()
        frequency = self.custom_penalty_frequency
        if frequency == 'system':
            frequency = settings.penalty_frequency

        if self.penalty_type == 'none':
            return {'type': 'none', 'rate': 0, 'lumpsum': 0, 'frequency': frequency}

        if self.penalty_type == 'percentage':
            return {
                'type': 'percentage',
                'rate': self.custom_penalty_rate or Decimal('12'),
                'lumpsum': 0,
                'frequency': frequency,
            }

        if self.penalty_type == 'lumpsum':
            return {
                'type': 'lumpsum',
                'rate': 0,
                'lumpsum': self.custom_penalty_lumpsum or Decimal('0'),
                'frequency': frequency,
            }

        # Default: use system settings
        return {
            'type': settings.penalty_type,
            'rate': settings.penalty_rate_pa,
            'lumpsum': settings.penalty_lumpsum,
            'frequency': settings.penalty_frequency,
        }
