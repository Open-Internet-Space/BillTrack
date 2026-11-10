"""Temporary SMTP previews: editable text, signed balance snapshot, no draft storage."""
import hashlib
import json
from django import forms
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail.message import sanitize_address
from django.forms import formset_factory
from django.utils import timezone
from ..email_drafts.service import generate
from rest_framework.exceptions import ValidationError as MergeValidationError
from ..email_drafts.validation import validate_header, validate_recipients
from ..models import EmailTemplate

MAX_PREVIEWS = 25
SALT = 'billtrack-reminder-preview-v1'


def validate_sender():
    try:
        sanitize_address(settings.DEFAULT_FROM_EMAIL, 'utf-8')
    except ValueError:
        raise ValidationError('Set DEFAULT_FROM_EMAIL to a valid sender, such as "Office <mailbox@example.com>", in the private .env and restart BillTrack.')


class TemplateSelectionForm(forms.Form):
    template = forms.ModelChoiceField(queryset=EmailTemplate.objects.filter(active=True), label='Email template')


class EmailPreviewForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput, max_length=2048)
    to = forms.EmailField(label='To', max_length=254)
    cc = forms.CharField(label='CC', required=False, max_length=2000, validators=[validate_recipients])
    subject = forms.CharField(max_length=240, validators=[validate_header])
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 16}), max_length=100000, strip=False)


EmailPreviewFormSet = formset_factory(EmailPreviewForm, extra=0, min_num=1, validate_min=True,
                                    max_num=MAX_PREVIEWS, validate_max=True, absolute_max=MAX_PREVIEWS)


def group_fingerprint(group, today):
    from .service import smtp_fingerprint
    snapshot = {'uuid': group['uuid'], 'email': group['email'], 'name': group['allottee'].name,
                'description': group['allottee'].allotment_description, 'items': group['items'],
                'total': str(group['total']), 'date': str(today), 'smtp': smtp_fingerprint()}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def prepare_messages(selected, template, user_id, today=None):
    from .service import preview
    today = today or timezone.localdate()
    if not selected or len(selected) > MAX_PREVIEWS:
        raise ValidationError(f'Select between 1 and {MAX_PREVIEWS} allottees for a preview.')
    if not template.active:
        raise ValidationError('Choose an active email template.')
    validate_sender()
    groups = {group['uuid']: group for group in preview(today)[0]}
    if not set(selected).issubset(groups):
        raise ValidationError('Some selected reminders are no longer eligible. Refresh the list and prepare a new preview.')
    prepared = []
    for uuid in sorted(selected):
        group = groups[uuid]
        try:
            merged = generate(group['allottee'].pk, [item['bill_id'] for item in group['items']], template)
        except MergeValidationError:
            raise ValidationError('The template could not be merged. Check its length and refresh the selected bills.')
        prepared.append({'token': signing.dumps({'uuid': uuid, 'fingerprint': group_fingerprint(group, today),
                                                'user_id': user_id}, salt=SALT, compress=True),
                         **{field: merged[field] for field in ('to', 'cc', 'subject', 'body')}})
    return prepared


def confirmed_messages(values, user_id, today):
    from .service import preview
    if not user_id or not values or len(values) > MAX_PREVIEWS:
        raise ValidationError('Prepare and review an email preview before sending.')
    validate_sender()
    groups = {group['uuid']: group for group in preview(today)[0]}
    confirmed = {}
    for payload in values:
        form = EmailPreviewForm(payload)
        if not form.is_valid():
            raise ValidationError('Correct the To, CC, subject or body fields before sending. Your entries have been kept.')
        data = form.cleaned_data
        try:
            token = signing.loads(data['token'], salt=SALT, max_age=3600)
        except signing.BadSignature:
            raise ValidationError('This preview expired or is invalid. Copy any edits you need, then prepare a new preview.')
        uuid = token.get('uuid')
        group = groups.get(uuid)
        if token.get('user_id') != user_id or not group or token.get('fingerprint') != group_fingerprint(group, today):
            raise ValidationError('Balances, bill details, recipients or SMTP settings changed, or a reminder was already submitted. Copy your edits and prepare a new preview.')
        if uuid in confirmed:
            raise ValidationError('The same allottee cannot appear twice in one confirmation.')
        confirmed[uuid] = {**data, 'fingerprint': token['fingerprint']}
    return confirmed
