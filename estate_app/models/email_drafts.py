from django.db import models
from ..email_drafts.validation import validate_template, validate_header, HELP

class EmailTemplate(models.Model):
    name=models.CharField(max_length=120,unique=True)
    subject=models.CharField(max_length=240,validators=[validate_header,validate_template],help_text=HELP)
    body=models.TextField(max_length=30000,validators=[validate_template],help_text=HELP)
    active=models.BooleanField(default=True)

    class Meta:
        ordering=['name']

    def __str__(self):
        return self.name
