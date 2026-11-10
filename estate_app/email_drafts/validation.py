"""Literal email placeholders and recipient validation; no template execution."""
from string import Formatter
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

PLACEHOLDERS=('allottee_name','organisation_name','signing_authority','preparation_date','bill_details','outstanding_total')
HELP='Available placeholders: '+', '.join('{'+key+'}' for key in PLACEHOLDERS)

def validate_template(value):
    try:
        for _,name,spec,conversion in Formatter().parse(value):
            if name is not None and (name not in PLACEHOLDERS or spec or conversion):
                raise ValueError('Unsupported placeholder')
    except ValueError:
        raise ValidationError(HELP)

def validate_header(value):
    if '\r' in value or '\n' in value:
        raise ValidationError('Use a single line without newline characters.')

def validate_recipients(value):
    validate_header(value)
    if not value.strip():
        return
    for address in value.replace(';',',').split(','):
        if not address.strip():
            raise ValidationError('Enter email addresses separated by commas or semicolons.')
        validate_email(address.strip())
