"""Literal email placeholders and recipient validation; no template execution."""
from string import Formatter
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

PLACEHOLDER_DETAILS=(
    ('allottee_name', 'Allottee name', 'The selected person or business name.', False),
    ('allotment_description', 'Allotment description', 'The shop, premises or other identifier for this allotment; blank if not entered.', False),
    ('organisation_name', 'Organisation name', 'The organisation name configured in System Settings.', False),
    ('signing_authority', 'Signing authority', 'The signing authority configured in System Settings; may contain multiple lines.', True),
    ('preparation_date', 'Preparation date', 'The date this email is generated.', False),
    ('bill_details', 'Bill details', 'References, billing periods, receipt/due status and remaining amounts for selected bills.', True),
    ('outstanding_total', 'Outstanding total', 'The total outstanding for selected bills in INR.', False),
)
PLACEHOLDERS=tuple(item[0] for item in PLACEHOLDER_DETAILS)
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
