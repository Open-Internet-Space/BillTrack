"""Append-only security receipts and reviewed liability debits."""
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, router, transaction
from django.utils import timezone

from .estate import Allotment


class SecurityMovementQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        if kwargs:
            raise ValidationError('Security receipts cannot use conflict-ignoring bulk writes.')
        with transaction.atomic(using=self.db):
            result = list(objs)
            for movement in result:
                movement.save(using=self.db, force_insert=True)
            return result

    def update(self, **kwargs):
        raise ValidationError('Security movements are retained financial history and cannot be rewritten.')

    def delete(self):
        raise ValidationError('Security movements are retained financial history and cannot be deleted.')


class SecurityMovement(models.Model):
    objects = SecurityMovementQuerySet.as_manager()
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    original_award = models.ForeignKey(Allotment, on_delete=models.PROTECT, related_name='security_movements')
    kind = models.CharField(max_length=15, choices=[('received','Received'), ('refunded','Refunded'),
        ('applied','Applied to obligation'), ('forfeited','Forfeited by approval')])
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    effective_date = models.DateField()
    reference = models.CharField(max_length=250)
    reason = models.TextField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='security_movements')
    operation_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    applied_bill = models.ForeignKey('Bill', on_delete=models.PROTECT, null=True, blank=True, related_name='security_applications')
    applied_charge = models.ForeignKey('EstateCharge', on_delete=models.PROTECT, null=True, blank=True, related_name='security_applications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['effective_date','pk']
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='estate_security_positive'),
            models.CheckConstraint(check=(models.Q(kind='applied',operation_id__isnull=False)
                & (models.Q(applied_bill__isnull=False,applied_charge__isnull=True)
                   | models.Q(applied_bill__isnull=True,applied_charge__isnull=False)))
                | (~models.Q(kind='applied') & models.Q(applied_bill__isnull=True,applied_charge__isnull=True)),
                name='estate_security_target'),
        ]

    def __str__(self):
        return f'{self.original_award.shop.code} · {self.kind} · {self.amount} · {self.reference}'

    def clean(self):
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if any(getattr(previous, field.attname) != getattr(self, field.attname)
                   for field in self._meta.concrete_fields if field.name != 'id'):
                raise ValidationError('Security movements are immutable; retain the original financial evidence.')
            return
        if not self.original_award_id or self.amount is None or not self.recorded_by_id:
            return
        root = self.original_award
        if root.renewal_of_id:
            raise ValidationError('Security belongs to the original award, not a separate renewal deposit.')
        if not self.reference.strip() or not self.reason.strip():
            raise ValidationError('Record the actual payment/approval reference and reason.')
        if self.effective_date and (self.effective_date < root.letter_issued_on or self.effective_date > timezone.localdate()):
            raise ValidationError('A security movement must be dated between the original letter and today.')
        if self.kind != 'received':
            if not (getattr(self, '_security_authorized', False) and self.recorded_by.is_superuser):
                raise ValidationError('Use the reviewed superuser action for a security debit.')
            if self.amount > root.security_held:
                raise ValidationError('This movement exceeds security currently held.')
            if self.effective_date:
                history = list(root.security_movements.values_list('effective_date','pk','kind','amount'))
                history.append((self.effective_date,float('inf'),self.kind,self.amount))
                held = Decimal('0')
                for _, _, kind, amount in sorted(history):
                    held += amount if kind == 'received' else -amount
                    if held < 0:
                        raise ValidationError('This effective date would make a historical security balance negative.')
        if self.kind == 'applied':
            target = self.applied_bill or self.applied_charge
            term = target.allotment if target else None
            if term is None or term.original_award.pk != root.pk or term.tenant_id != root.tenant_id:
                raise ValidationError('Apply security only within the same original award, renewal chain and allottee.')
            if self.applied_bill_id and target.is_draft:
                raise ValidationError('Raise the invoice before applying security.')
            outstanding = target.balance_due + (target.penalty if self.applied_bill_id else Decimal('0'))
            if self.amount > outstanding:
                raise ValidationError('This application exceeds the target obligation balance.')

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            Allotment.objects.using(using).filter(pk=self.original_award_id).update(actual_area=models.F('actual_area'))
            self._state.fields_cache.pop('original_award',None)
            self._state.fields_cache.pop('applied_bill',None)
            self._state.fields_cache.pop('applied_charge',None)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Security movements are retained financial history and cannot be deleted.')
