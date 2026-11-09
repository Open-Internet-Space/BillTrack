from django.core.exceptions import ValidationError
from django.db import models

class ReminderSettings(models.Model):
    automatic_enabled=models.BooleanField(default=False)
    verified_config=models.CharField(max_length=64,blank=True,editable=False)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name_plural='Email reminder settings'
    def save(self,*args,**kwargs):
        self.pk=1
        super().save(*args,**kwargs)
    def clean(self):
        from ..reminders.service import mail_configured,smtp_fingerprint
        if self.automatic_enabled and (not mail_configured() or self.verified_config!=smtp_fingerprint()):
            raise ValidationError('Send a successful test email using the current SMTP settings before enabling automatic reminders.')
    def __str__(self):
        return 'Email reminder settings'

class ReminderDelivery(models.Model):
    STATUS=[('preparing','Preparing — interrupted runs need review'),('sending','Sending — interrupted runs need review'),
            ('accepted','Accepted by mail server'),('failed','Failed — retry allowed'),('review','Needs review — do not resend'),
            ('skipped','Skipped after recheck')]
    allottee=models.ForeignKey('Tenant',null=True,blank=True,on_delete=models.SET_NULL)
    allottee_uuid=models.UUIDField()
    allottee_name=models.CharField(max_length=200)
    send_date=models.DateField()
    recipient=models.EmailField()
    items=models.JSONField(default=list)
    status=models.CharField(max_length=12,choices=STATUS,default='preparing')
    attempts=models.PositiveIntegerField(default=1)
    error=models.CharField(max_length=300,blank=True)
    reviewed_by=models.CharField(max_length=150,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['allottee_uuid','send_date'],name='reminder_one_allottee_day')]
    def __str__(self):
        return f'{self.send_date}: {self.allottee_name} — {self.get_status_display()}'
