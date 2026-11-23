from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
from .billing import Bill


def refresh_bills(bill_ids, using):
    for bill in Bill.objects.using(using).filter(pk__in=bill_ids):
        bill.update_status()


class PaymentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if {'source', 'operation_id'} & kwargs.keys():
            raise ValidationError('Receipt sources and paired security operation IDs cannot be rewritten.')
        financial = {'bill', 'bill_id', 'amount', 'penalty_paid', 'payment_date', 'source', 'operation_id', 'recorded_by', 'recorded_by_id'}
        if financial & kwargs.keys() and self.filter(source='security_application').exists():
            raise ValidationError('Paired security settlements cannot be rewritten through bulk corrections.')
        if not financial & kwargs.keys():
            return super().update(**kwargs)
        with transaction.atomic(using=self.db):
            original = list(self.values_list('pk', 'bill_id'))
            count = super().update(**kwargs)
            changed = list(self.model.objects.using(self.db).filter(pk__in=[pk for pk, _ in original]))
            for payment in changed:
                payment.full_clean()
            refresh_bills({bill_id for _, bill_id in original} | {row.bill_id for row in changed}, self.db)
            return count

    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        for payment in objs:
            payment.full_clean(validate_unique=not (kwargs.get('update_conflicts') or kwargs.get('ignore_conflicts')))
        with transaction.atomic(using=self.db):
            previous_bills = set(self.model.objects.using(self.db).filter(
                models.Q(uuid__in=[obj.uuid for obj in objs]) | models.Q(pk__in=[obj.pk for obj in objs if obj.pk])
            ).values_list('bill_id', flat=True))
            result = super().bulk_create(objs, **kwargs)
            refresh_bills(previous_bills | {obj.bill_id for obj in objs}, self.db)
            return result

    def delete(self):
        with transaction.atomic(using=self.db):
            if self.filter(source='security_application').exists():
                raise ValidationError('Paired security settlements cannot be deleted as ordinary receipts.')
            bill_ids = set(self.values_list('bill_id', flat=True))
            result = super().delete()
            refresh_bills(bill_ids, self.db)
            return result


class Payment(models.Model):
    objects = PaymentQuerySet.as_manager()
    uuid         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    bill         = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount       = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount received")
    payment_date = models.DateField(default=timezone.localdate)
    penalty_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text="Penalty component (if any)")
    receipt_no   = models.CharField(max_length=50, blank=True, help_text="Cash receipt / Cheque number")
    notes        = models.TextField(blank=True)
    source       = models.CharField(max_length=25, default='receipt', choices=[
        ('receipt', 'Receipt'), ('security_application', 'Reviewed security application')])
    operation_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    recorded_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_recorded')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        constraints = [models.CheckConstraint(check=(models.Q(source='receipt',operation_id__isnull=True)
            | models.Q(source='security_application',operation_id__isnull=False)), name='estate_payment_source')]

    def __str__(self):
        return f"₹{self.amount} | {self.bill.invoice_no} | {self.payment_date}"

    def clean(self):
        from ..estate.security import validate_security_pair
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk and not self._state.adding else None
        validate_security_pair(self, previous, 'bill')
        if self.amount < 0 or (self.amount == 0 and self.penalty_paid == 0):
            raise ValidationError({'amount': 'Enter a principal or penalty payment'})
        if self.penalty_paid < 0:
            raise ValidationError({'penalty_paid': 'Penalty cannot be negative'})
        if self.bill_id and self.bill.billing_policy == 'notices_368_369':
            if not self.bill.raised_date:
                raise ValidationError({'bill': 'Raise the notice invoice before recording a receipt.'})
            if self.payment_date < self.bill.raised_date or self.payment_date > timezone.localdate():
                raise ValidationError({'payment_date': 'A notice receipt must be dated between invoice raising and today.'})

    @transaction.atomic
    def save(self, *args, **kwargs):
        old_bill_id = Payment.objects.filter(pk=self.pk).values_list('bill_id', flat=True).first() if self.pk else None
        self.full_clean()
        super().save(*args, **kwargs)
        # Automatically recalculate bill status (backend logic)
        refresh_bills({self.bill_id, old_bill_id}, self._state.db)
        if 'bill' in self._state.fields_cache:
            self.bill.refresh_from_db()

    def delete(self, *args, **kwargs):
        if type(self).objects.filter(pk=self.pk, source='security_application').exists():
            raise ValidationError('Paired security settlements cannot be deleted as ordinary receipts.')
        return super().delete(*args, **kwargs)


@receiver(post_delete, sender=Payment)
def payment_deleted(sender, instance, using, origin, **kwargs):
    # QuerySet deletion handles its set once; parent cascades remove the bills too.
    if isinstance(origin, Payment):
        refresh_bills({instance.bill_id}, using)
