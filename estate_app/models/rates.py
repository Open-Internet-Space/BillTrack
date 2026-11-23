from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, router, transaction
from django.db.models import F

from .estate import Allotment


class RentRevision(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    original_award = models.ForeignKey(Allotment, on_delete=models.PROTECT, related_name='rent_revisions')
    effective_date = models.DateField(help_text='Explicit as-of date for the initial accepted rate; effective date for later approvals.')
    rate = models.DecimalField(max_digits=12, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    approval_reference = models.CharField(max_length=250)
    reason = models.TextField()
    exception_reference = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['original_award__shop__code', 'effective_date', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['original_award', 'effective_date'], name='estate_rate_effective_unique'),
            models.CheckConstraint(check=models.Q(rate__gt=0), name='estate_rate_positive'),
        ]

    def __str__(self):
        return f'{self.original_award.shop.code} · {self.effective_date} · {self.rate}/sq ft'

    def clean(self):
        if not self.original_award_id or not self.effective_date or self.rate is None:
            return
        if self.original_award.renewal_of_id:
            raise ValidationError({'original_award': 'Rates belong to the original award; renewals share its schedule.'})
        if self.pk and self.bills.exists():
            previous = type(self).objects.get(pk=self.pk)
            if any(getattr(previous, key) != getattr(self, key) for key in ('original_award_id', 'effective_date', 'rate')):
                raise ValidationError('A billed rate cannot be moved or rewritten; record a later approved revision.')
        if not self.approval_reference.strip() or not self.reason.strip():
            raise ValidationError('Record the rate approval reference and reason.')
        rows = list(type(self).objects.filter(original_award_id=self.original_award_id).exclude(pk=self.pk)) + [self]
        rows.sort(key=lambda row: (row.effective_date, row.pk or 0))
        from ..estate.billing import annual_revisions
        for previous, current in zip(rows, rows[1:]):
            if previous.effective_date == current.effective_date:
                raise ValidationError({'effective_date': 'This award already has a rate for this effective date.'})
            due = annual_revisions(previous.rate, previous.effective_date, current.effective_date)
            if not current.exception_reference.strip() and (len(due) != 1
                    or current.effective_date != due[0]['effective_date'] or current.rate != due[0]['rate']):
                raise ValidationError('Approve the next 5% April revision in order, or record an authorized exception reference.')

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            Allotment.objects.using(using).filter(pk=self.original_award_id).update(actual_area=F('actual_area'))
            self.full_clean()
            return super().save(*args, **kwargs)
