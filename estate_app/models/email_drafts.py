from django.db import models
from ..email_drafts.validation import validate_template, validate_header, validate_recipients, HELP

class EmailTemplate(models.Model):
    name=models.CharField(max_length=120,unique=True)
    subject=models.CharField(max_length=240,validators=[validate_header,validate_template],help_text=HELP)
    body=models.TextField(max_length=30000,validators=[validate_template],help_text=HELP)
    active=models.BooleanField(default=True)
    cc = models.CharField(max_length=2000, blank=True, default='', validators=[validate_recipients],
                          help_text='Template CC addresses. Leave blank to use the System Settings defaults.')
    manual_only = models.BooleanField(default=False, help_text='Offer this template only in manual email drafts.')

    class Meta:
        ordering=['name']

    def __str__(self):
        return self.name
