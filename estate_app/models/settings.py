from ..email_drafts.validation import validate_recipients
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator


def validate_invoice_logo_size(upload):
    if upload.size > 2 * 1024 * 1024:
        raise ValidationError('Choose a logo smaller than 2 MB.')


class SystemSettings(models.Model):
    """System-wide configuration - Only one record should exist"""

    premises_enabled = models.BooleanField('Enable Premises', default=False,
        help_text='Show the premises register and allow optional links on allotment terms.')
    allotment_details_enabled = models.BooleanField('Show additional allotment details', default=False,
        help_text='Show notice, measurement, charge approval and possession or handover fields on allotment forms.')

    new_signups_enabled = models.BooleanField('New signups', default=True)
    bill_email_enabled = models.BooleanField('Bills email communication', default=True,
        help_text='Allow BillTrack to send bill reminder emails.')
    bill_email_copy_enabled = models.BooleanField('Bills email format for copying', default=True,
        help_text='Allow staff to generate and copy bill email drafts.')

    @classmethod
    def feature_enabled(cls, name):
        value = cls.objects.filter(pk=1).values_list(name, flat=True).first()
        return cls._meta.get_field(name).get_default() if value is None else value

    @classmethod
    def premises_are_enabled(cls):
        return cls.objects.filter(pk=1, premises_enabled=True).exists()

    # Penalty Settings
    PENALTY_TYPE_CHOICES = [
        ('percentage', 'Percentage (% per annum)'),
        ('lumpsum', 'Lumpsum (fixed amount)'),
    ]
    PENALTY_FREQUENCY_CHOICES = [
        ('day', 'Per Day'),
        ('month', 'Per Month'),
        ('year', 'Per Year'),
    ]
    penalty_type = models.CharField(max_length=20, choices=PENALTY_TYPE_CHOICES,
                                    default='percentage', help_text="Type of penalty calculation")
    penalty_rate_pa = models.DecimalField(max_digits=5, decimal_places=2, default=12.00,
                                         help_text="Penalty rate % per annum (if percentage type)")
    penalty_lumpsum = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         help_text="Fixed penalty amount (if lumpsum type)")
    penalty_frequency = models.CharField(max_length=10, choices=PENALTY_FREQUENCY_CHOICES, default='year',
                                         help_text="Penalty frequency for rate/lumpsum")

    # GST Settings
    gst_applicable = models.BooleanField(default=True, help_text="Enable GST on rent")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00,
                                   help_text="GST rate % (e.g., 18.00 for 18%)")
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9.00,
                                    help_text="CGST rate % (half of GST)")
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9.00,
                                    help_text="SGST rate % (half of GST)")

    letterhead_logo = models.ImageField(
        upload_to='invoice-branding/', blank=True,
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg', 'webp']), validate_invoice_logo_size],
        help_text='PNG, JPEG or WebP, up to 2 MB. Leave empty to keep the current logo. A generic BillTrack logo is used until you upload one.')
    letterhead_name = models.CharField(max_length=250, blank=True, default='', help_text='Required before printing invoices.')
    letterhead_department = models.CharField(max_length=250, blank=True, default='')
    letterhead_address = models.TextField(blank=True, default='')
    signing_authority = models.TextField(blank=True, default='',
                                         help_text='Enter each line separately, e.g. designation, division and institute. Two or three lines are supported.')
    billed_from = models.TextField(blank=True, default='',
                                   help_text='Optional sender name and address, one line per entry. Leave blank to preserve the printed reference layout.')
    supplier_gstin = models.CharField('Supplier GSTIN', max_length=30, blank=True, default='')
    place_of_supply = models.CharField(max_length=150, blank=True, default='')
    invoice_note = models.TextField(blank=True, default='Due date is 5 day from date of issue of this invoice. Penalty / interest, if applicable, will be calculated as per the vendor billing profile. This invoice is computer-generated. GST applicable on rent component only as per GST Act 2017.',
                                    help_text='Printed wording only; change penalty/GST settings separately to change calculations.')
    copy_to = models.TextField(blank=True, help_text='One recipient per line. Leave blank to omit Copy to.')
    reference_number_format = models.CharField(max_length=200, default='REF/_____/{year}',
                                              help_text='Used when a dispatch reference is blank. {year} uses the issue year (or bill year if not issued). Example: REF/_____/{year}. Saved references and internal invoice numbers are unchanged.')
    bank_details = models.TextField(blank=True, default='',
                                    help_text='One entry per line; account numbers are kept as text, including leading zeroes.')
    invoice_remarks = models.TextField(blank=True, default='')

    email_draft_cc = models.CharField(max_length=2000, blank=True, default='', validators=[validate_recipients], help_text='Default email draft CC addresses, separated by commas or semicolons.')
    email_draft_bcc = models.CharField(max_length=2000, blank=True, default='', validators=[validate_recipients], verbose_name='Default email draft BCC', help_text='Separate addresses with commas or semicolons.')

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f"System Settings (Updated: {self.updated_at.strftime('%d-%b-%Y')})"

    def save(self, *args, **kwargs):
        # Ensure only one settings record exists
        if not self.pk and SystemSettings.objects.exists():
            raise ValidationError('Only one System Settings record allowed. Please edit the existing one.')
        return super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create system settings"""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
