from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
from .billing import Bill


class Payment(models.Model):
    uuid         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    bill         = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount       = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount received")
    payment_date = models.DateField(default=timezone.localdate)
    penalty_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text="Penalty component (if any)")
    receipt_no   = models.CharField(max_length=50, blank=True, help_text="Cash receipt / Cheque number")
    notes        = models.TextField(blank=True)
    recorded_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_recorded')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"₹{self.amount} | {self.bill.invoice_no} | {self.payment_date}"

    def clean(self):
        if self.amount < 0 or (self.amount == 0 and self.penalty_paid == 0):
            raise ValidationError({'amount': 'Enter a principal or penalty payment'})
        if self.penalty_paid < 0:
            raise ValidationError({'penalty_paid': 'Penalty cannot be negative'})

    def save(self, *args, **kwargs):
        old_bill_id = Payment.objects.filter(pk=self.pk).values_list('bill_id', flat=True).first() if self.pk else None
        super().save(*args, **kwargs)
        # Automatically recalculate bill status (backend logic)
        self.bill.update_status()
        if old_bill_id and old_bill_id != self.bill_id:
            Bill.objects.get(pk=old_bill_id).update_status()
