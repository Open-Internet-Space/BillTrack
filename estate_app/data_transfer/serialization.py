import base64
import binascii
import copy
import json
from datetime import datetime
from pathlib import Path
from django import forms
from django.contrib.auth.models import User
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.serializers.base import DeserializationError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from ..models import (Allotment, AllotmentRequirement, Bill, EstateCharge, EstateChargePayment,
    Payment, RentRevision, SecurityMovement, Shop, SystemSettings, Tenant, validate_invoice_logo_size)


LEGACY_MODELS = (Tenant, Bill, Payment, SystemSettings)
MODELS = (Tenant, Shop, Allotment, AllotmentRequirement, RentRevision, Bill, EstateCharge,
          SecurityMovement, Payment, EstateChargePayment, SystemSettings)


MODEL_MAP = {model._meta.label_lower: model for model in MODELS}


USER_FIELDS = {'created_by', 'recorded_by', 'updated_by', 'dispatch_sender', 'verified_by', 'waived_by'}


MAX_IMPORT_SIZE = 25 * 1024 * 1024


def export_data():
    records = []
    usernames = dict(User.objects.values_list('pk', 'username'))
    for model in MODELS:
        for record in serializers.serialize('python', model.objects.order_by('pk')):
            for field in USER_FIELDS & record['fields'].keys():
                record['fields'][field] = usernames.get(record['fields'][field])
            # File paths are local; the actual validated image travels separately.
            if model is SystemSettings:
                record['fields']['letterhead_logo'] = ''
            records.append(record)
    logo = None
    config = SystemSettings.objects.first()
    if config and config.letterhead_logo:
        with config.letterhead_logo.open('rb') as stream:
            logo = {'name': Path(config.letterhead_logo.name).name,
                    'content': base64.b64encode(stream.read()).decode('ascii')}
    return {'format': 'billtrack-data', 'version': 2, 'exported_at': timezone.now(),
            'records': records, 'logo': logo}


class BackupJSONEncoder(DjangoJSONEncoder):
    def default(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return super().default(value)


def export_bytes():
    return json.dumps(export_data(), cls=BackupJSONEncoder, indent=2).encode('utf-8')


def validate_data(data):
    if (not isinstance(data, dict) or data.get('format') != 'billtrack-data'
            or type(data.get('version')) is not int or data['version'] not in (1, 2)
            or not isinstance(data.get('records'), list) or 'logo' not in data):
        raise ValidationError('Choose a version 1 or version 2 BillTrack data export (JSON).')
    records = copy.deepcopy(data['records'])
    ids = {label: set() for label in MODEL_MAP}
    usernames = dict(User.objects.values_list('username', 'pk'))
    for record in records:
        if (not isinstance(record, dict) or set(record) != {'model', 'pk', 'fields'}
                or not isinstance(record['model'], str) or record['model'] not in MODEL_MAP
                or type(record['pk']) is not int or record['pk'] < 1
                or not isinstance(record['fields'], dict)):
            raise ValidationError('The export contains an invalid record or unsupported model.')
        label, fields = record['model'], record['fields']
        if data['version']==1 and MODEL_MAP[label] not in LEGACY_MODELS:
            raise ValidationError('Version 1 supports legacy records only; use a complete version 2 estate export.')
        if data['version']==1 and label == 'estate_app.tenant':
            fields.setdefault('allotment_description', '')
        if data['version']==1 and label == 'estate_app.bill':
            fields.setdefault('billing_policy', 'legacy_receipt')
            for field in ('raised_date', 'email_dispatched_at', 'dispatch_sender', 'rent_revision', 'rate_snapshot', 'area_snapshot'):
                fields.setdefault(field, None)
            for field in ('dispatch_recipient', 'dispatch_message_reference', 'rent_revision_reference', 'rent_override_reason', 'rate_exception_reference'):
                fields.setdefault(field, '')
            fields.setdefault('allotment', None)
            fields.setdefault('billing_category', 'legacy')
            for field in ('full_month_rent', 'holiday_start_date', 'holiday_end_date'):
                fields.setdefault(field, None)
            fields.setdefault('holiday_closed_days', 0)
            fields.setdefault('holiday_waiver', '0.00')
            if fields['allotment'] is not None or fields['rent_revision'] is not None or fields['billing_policy']!='legacy_receipt':
                raise ValidationError('A version 1 file cannot restore linked estate or notice-policy evidence. Use a complete version 2 export.')
        if data['version']==1 and label == 'estate_app.payment':
            fields.setdefault('source','receipt')
            fields.setdefault('operation_id',None)
            if fields['source']!='receipt' or fields['operation_id'] is not None:
                raise ValidationError('Security settlements require a complete version 2 estate export.')
        if data['version']==1 and label == 'estate_app.systemsettings':
            fields.setdefault('email_draft_cc', '')
        if label == 'estate_app.tenant':
            fields.setdefault('contract_draft', {})
        if label == 'estate_app.systemsettings':
            fields.setdefault('email_draft_bcc', '')
            fields.setdefault('premises_enabled', False)
            fields.setdefault('allotment_details_enabled', False)
            for flag in ('new_signups_enabled', 'bill_email_enabled', 'bill_email_copy_enabled'):
                fields.setdefault(flag, True)
        if label == 'estate_app.allotment':
            fields.setdefault('rent_basis', 'area')
            fields.setdefault('carry_forward_deposit', False)
            fields.setdefault('security_timing', '')
            fields.setdefault('security_offer_date', None)
            fields.setdefault('exception_reason', '')
        expected = {field.name for field in MODEL_MAP[label]._meta.fields if not field.primary_key}
        if set(fields) != expected or record['pk'] in ids[label]:
            raise ValidationError('The export has duplicate records or missing/unknown fields.')
        ids[label].add(record['pk'])
        for field in USER_FIELDS & fields.keys():
            if fields[field] is not None and not isinstance(fields[field], str):
                raise ValidationError('User references must be usernames, not local account IDs.')
            fields[field] = usernames.get(fields[field])
            if fields[field] is None and not MODEL_MAP[label]._meta.get_field(field).null:
                raise ValidationError(f'{label}.{field} requires a matching local username; financial attribution cannot be discarded.')
    if len(ids['estate_app.systemsettings']) > 1:
        raise ValidationError('An export can contain only one system settings record.')
    for record in records:
        model = MODEL_MAP[record['model']]
        for field in model._meta.fields:
            if not field.is_relation or field.remote_field.model is User:
                continue
            value = record['fields'][field.name]
            if value is None and field.null:
                continue
            target = field.remote_field.model._meta.label_lower
            if type(value) is not int or value not in ids[target]:
                raise ValidationError(f'The export contains a missing {target} reference in {record["model"]}.{field.name}.')
        if record['model'] == 'estate_app.systemsettings' and record['fields']['letterhead_logo']:
            raise ValidationError('Logo file paths cannot be imported. Export the image with BillTrack.')
    try:
        objects = list(serializers.deserialize('python', records))
        imported = {model:{item.object.pk:item.object for item in objects if type(item.object) is model} for model in MODELS}
        estate_graph = any(type(item.object) not in LEGACY_MODELS for item in objects)
        identities = {label: set() for label in MODEL_MAP}
        invoice_numbers = set()
        for item in objects:
            obj = item.object
            for field in obj._meta.fields:
                if field.is_relation and field.remote_field.model in imported:
                    value = getattr(obj,field.attname)
                    if value is not None:
                        setattr(obj,field.name,imported[field.remote_field.model][value])
            excluded = [field.name for field in obj._meta.fields if field.is_relation]+['letterhead_logo']
            if estate_graph:
                obj.clean_fields(exclude=excluded)
            else:
                obj.full_clean(exclude=excluded,validate_unique=False,validate_constraints=False)
            if isinstance(obj, Bill):
                if obj.full_month_rent is not None:
                    from ..estate.billing import holiday_rent
                    expected = holiday_rent(obj.full_month_rent, obj.year, obj.month,
                                            obj.holiday_start_date, obj.holiday_end_date)
                    if (obj.rent != expected['applicable_rent'] or obj.holiday_closed_days != expected['closed_days']
                            or obj.holiday_waiver != expected['waiver_amount']):
                        raise ValidationError('Holiday dates, original rent and saved waiver amounts do not agree.')
                elif obj.holiday_closed_days or obj.holiday_waiver:
                    raise ValidationError('A holiday waiver requires the original full-month rent.')
            identity = ((obj.tenant_id, obj.allotment_id, obj.year, obj.month) if isinstance(obj, Bill)
                        else getattr(obj, 'uuid', 1))
            seen = identities[obj._meta.label_lower]
            if identity in seen:
                raise ValidationError('The export contains duplicate UUIDs or billing periods.')
            seen.add(identity)
            if isinstance(obj, Bill) and obj.invoice_no:
                if obj.invoice_no in invoice_numbers:
                    raise ValidationError('The export contains duplicate invoice numbers.')
                invoice_numbers.add(obj.invoice_no)
    except (DeserializationError, TypeError, ValueError, OverflowError) as error:
        raise ValidationError('The export contains invalid field values.') from error
    if estate_graph:
        from .graph import validate_graph
        try:
            validate_graph(objects)
        except (TypeError,ValueError,OverflowError,RecursionError) as error:
            raise ValidationError('The export contains invalid estate dates or values.') from error
    logo = None
    if data['logo'] is not None:
        image = data['logo']
        if (not ids['estate_app.systemsettings'] or not isinstance(image, dict)
                or set(image) != {'name', 'content'} or not isinstance(image['name'], str)
                or not isinstance(image['content'], str) or len(image['content']) > 3 * 1024 * 1024):
            raise ValidationError('The export contains an invalid letterhead logo.')
        try:
            logo = ContentFile(base64.b64decode(image['content'], validate=True), name=Path(image['name']).name)
            logo = forms.ImageField(validators=[validate_invoice_logo_size,
                SystemSettings._meta.get_field('letterhead_logo').validators[0]]).clean(logo)
        except (binascii.Error, ValueError) as error:
            raise ValidationError('The letterhead logo is not valid base64 image data.') from error
    return objects, logo
