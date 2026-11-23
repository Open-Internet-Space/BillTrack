"""Assessed estate obligations and their receipts, separate from monthly rent."""
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, router, transaction
from django.db.models import F, Sum
from django.utils import timezone

from .estate import Allotment


class EstateCharge(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    allotment = models.ForeignKey(Allotment, on_delete=models.PROTECT, related_name='charges')
    kind = models.CharField(max_length=25, choices=[('extension_fee', 'Extension fee'),
        ('incident_fine', 'Assessed incident fine'), ('damage_recovery', 'Damage recovery')])
    description = models.TextField()
    assessed_on = models.DateField()
    authority_reference = models.CharField(max_length=250)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))],
        help_text='Enter the explicitly reviewed tax, including zero; no tax treatment is inferred.')
    due_date = models.DateField()
    renewal_term = models.OneToOneField(Allotment, on_delete=models.PROTECT, null=True, blank=True,
        related_name='extension_fee_assessment', editable=False)
    waiver_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False,
                                        validators=[MinValueValidator(Decimal('0'))])
    waiver_reference = models.CharField(max_length=250, blank=True, editable=False)
    waiver_reason = models.TextField(blank=True, editable=False)
    waived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='estate_charge_waivers', editable=False)
    waived_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_operation_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='estate_assessments_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['allotment'], condition=models.Q(kind='extension_fee'),
                                    name='estate_single_extension_fee'),
            models.CheckConstraint(check=models.Q(net_amount__gte=0, tax_amount__gte=0, waiver_amount__gte=0),
                                   name='estate_charge_nonnegative'),
            models.CheckConstraint(check=(models.Q(net_amount__gt=0) | models.Q(tax_amount__gt=0)),
                                   name='estate_charge_positive_gross'),
            models.CheckConstraint(check=models.Q(waiver_amount__lte=F('net_amount') + F('tax_amount')),
                                   name='estate_waiver_within_gross'),
        ]

    def __str__(self):
        return f'{self.allotment.shop.code} · {self.get_kind_display()} · {self.authority_reference}'

    @property
    def gross_amount(self):
        return self.net_amount + self.tax_amount

    @property
    def amount_paid(self):
        if hasattr(self, '_amount_paid'):
            return self._amount_paid or Decimal('0')
        return sum((row.amount for row in self.payments.all()), Decimal('0'))

    @property
    def balance_due(self):
        return max(Decimal('0'), self.gross_amount - self.waiver_amount - self.amount_paid)

    @property
    def status(self):
        if self.balance_due == 0:
            return ('Waived' if not self.amount_paid else 'Settled') if self.waiver_amount else 'Paid'
        return 'Partial' if self.amount_paid or self.waiver_amount else 'Unpaid'

    @property
    def overdue(self):
        return self.due_date < timezone.localdate() and self.balance_due > 0

    def clean(self):
        if self.net_amount is None or self.tax_amount is None or not self.allotment_id:
            return
        term = self._state.fields_cache.get('allotment') or Allotment.objects.filter(pk=self.allotment_id).first()
        if term is None:
            return
        if not self.description.strip() or not self.authority_reference.strip():
            raise ValidationError('Record the assessment description and deciding authority/reference.')
        if self.assessed_on and self.assessed_on > timezone.localdate():
            raise ValidationError({'assessed_on': 'An assessment cannot be recorded as decided in the future.'})
        if self.due_date and self.assessed_on and self.due_date < self.assessed_on:
            raise ValidationError({'due_date': 'The deadline cannot precede the assessment decision.'})
        if self.pk and self.assessed_on and self.payments.filter(payment_date__lt=self.assessed_on).exists():
            raise ValidationError({'assessed_on': 'The corrected assessment cannot follow an existing receipt date.'})
        if self.gross_amount <= 0:
            raise ValidationError('An assessed charge must have a positive gross amount.')
        if self.kind == 'extension_fee':
            if term.extension_number >= 2:
                raise ValidationError('The original award already has its two permitted extensions.')
            if term.notice_governed and self.net_amount != Decimal('1000'):
                raise ValidationError({'net_amount': 'The notified extension fee is 1000 before explicitly reviewed tax.'})
        if self.renewal_term_id and (self.kind != 'extension_fee' or self.renewal_term.renewal_of_id != self.allotment_id):
            raise ValidationError('An extension fee must link only to the following term of this allotment.')
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk and not self._state.adding else None
        actor = getattr(self, '_decision_actor', None)
        reviewed = bool(actor and actor.is_superuser and getattr(self, '_decision_reason', '').strip())
        if previous:
            if (previous.allotment_id, previous.kind) != (self.allotment_id, self.kind):
                raise ValidationError('An assessed obligation cannot be moved to another allotment or charge kind.')
            if (previous.net_amount, previous.tax_amount) != (self.net_amount, self.tax_amount) and not reviewed:
                raise ValidationError('Use a reviewed superuser assessment correction to change assessed amounts.')
        waiver_fields = ('waiver_amount', 'waiver_reference', 'waiver_reason', 'waived_by_id', 'waived_at', 'last_operation_id')
        changed = any(getattr(previous, key) != getattr(self, key) for key in waiver_fields) if previous else bool(
            self.waiver_amount or self.waiver_reference or self.waiver_reason or self.waived_by_id or self.waived_at or self.last_operation_id)
        if changed and not reviewed:
            raise ValidationError('Waiver decisions require the reviewed superuser action.')
        if self.waiver_amount and (not self.waiver_reference.strip() or not self.waiver_reason.strip()
                                   or not self.waived_by_id or not self.waived_at):
            raise ValidationError('An approved waiver must retain its authority, reason, actor and time.')
        paid = (self.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')) if self.pk else Decimal('0')
        if paid + self.waiver_amount > self.gross_amount:
            raise ValidationError('Receipts plus the approved waiver cannot exceed the assessed gross amount.')

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            Allotment.objects.using(using).filter(pk=self.allotment_id).update(actual_area=F('actual_area'))
            self._state.fields_cache.pop('allotment', None)
            self.full_clean()
            return super().save(*args, **kwargs)


class EstateChargePaymentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if {'source', 'operation_id'} & kwargs.keys() or self.filter(source='security_application').exists():
            raise ValidationError('Paired security settlements cannot be rewritten through bulk corrections.')
        return super().update(**kwargs)

    def delete(self):
        if self.filter(source='security_application').exists():
            raise ValidationError('Paired security settlements cannot be deleted as ordinary receipts.')
        return super().delete()

    def bulk_create(self, objs, **kwargs):
        if kwargs:
            raise ValidationError('Charge receipts cannot use conflict-ignoring bulk writes.')
        with transaction.atomic(using=self.db):
            result = list(objs)
            for receipt in result:
                receipt.save(using=self.db, force_insert=True)
            return result


class EstateChargePayment(models.Model):
    objects = EstateChargePaymentQuerySet.as_manager()
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    charge = models.ForeignKey(EstateCharge, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateField(default=timezone.localdate)
    receipt_reference = models.CharField(max_length=250)
    source = models.CharField(max_length=25, default='receipt', choices=[('receipt', 'Receipt'),
        ('security_application', 'Reviewed security application')])
    operation_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='estate_charge_receipts')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['payment_date', 'pk']
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='estate_charge_receipt_positive'),
            models.CheckConstraint(check=(models.Q(source='receipt', operation_id__isnull=True)
                | models.Q(source='security_application', operation_id__isnull=False)), name='estate_charge_receipt_source'),
        ]

    def clean(self):
        if not self.charge_id or self.amount is None:
            return
        charge = self._state.fields_cache.get('charge') or EstateCharge.objects.filter(pk=self.charge_id).first()
        if charge is None:
            return
        if not self.receipt_reference.strip():
            raise ValidationError({'receipt_reference': 'Record the actual receipt or DD reference.'})
        if self.payment_date and not charge.assessed_on <= self.payment_date <= timezone.localdate():
            raise ValidationError({'payment_date': 'Receipt date must be between assessment and today.'})
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk and not self._state.adding else None
        if previous and previous.charge_id != self.charge_id:
            raise ValidationError('A receipt cannot be moved to another charge.')
        from ..estate.security import validate_security_pair
        validate_security_pair(self, previous, 'charge')
        other_paid = charge.payments.exclude(pk=self.pk).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        if other_paid + self.amount + charge.waiver_amount > charge.gross_amount:
            raise ValidationError({'amount': 'This receipt exceeds the remaining assessed balance.'})

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            EstateCharge.objects.using(using).filter(pk=self.charge_id).update(description=F('description'))
            self._state.fields_cache.pop('charge', None)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk, source='security_application').exists():
            raise ValidationError('Paired security settlements cannot be deleted as ordinary receipts.')
        return super().delete(*args, **kwargs)
