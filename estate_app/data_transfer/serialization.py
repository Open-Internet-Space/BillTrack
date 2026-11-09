import base64
import binascii
import copy
import json
from pathlib import Path
from django import forms
from django.contrib.auth.models import User
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.serializers.base import DeserializationError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from ..models import Bill, Payment, SystemSettings, Tenant, validate_invoice_logo_size


MODELS = (Tenant, Bill, Payment, SystemSettings)


MODEL_MAP = {model._meta.label_lower: model for model in MODELS}


USER_FIELDS = {'created_by', 'recorded_by', 'updated_by'}


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
    return {'format': 'billtrack-data', 'version': 1, 'exported_at': timezone.now(),
            'records': records, 'logo': logo}


def export_bytes():
    return json.dumps(export_data(), cls=DjangoJSONEncoder, indent=2).encode('utf-8')


def validate_data(data):
    if (not isinstance(data, dict) or data.get('format') != 'billtrack-data'
            or type(data.get('version')) is not int or data['version'] != 1
            or not isinstance(data.get('records'), list) or 'logo' not in data):
        raise ValidationError('Choose a version 1 BillTrack data export (JSON).')
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
        expected = {field.name for field in MODEL_MAP[label]._meta.fields if not field.primary_key}
        if set(fields) != expected or record['pk'] in ids[label]:
            raise ValidationError('The export has duplicate records or missing/unknown fields.')
        ids[label].add(record['pk'])
        for field in USER_FIELDS & fields.keys():
            if fields[field] is not None and not isinstance(fields[field], str):
                raise ValidationError('User references must be usernames, not local account IDs.')
            fields[field] = usernames.get(fields[field])
    if len(ids['estate_app.systemsettings']) > 1:
        raise ValidationError('An export can contain only one system settings record.')
    for record in records:
        for field, label in (('tenant', 'estate_app.tenant'), ('bill', 'estate_app.bill')):
            if field in record['fields']:
                value = record['fields'][field]
                if type(value) is not int or value not in ids[label]:
                    raise ValidationError('The export contains a missing allottee or bill reference.')
        if record['model'] == 'estate_app.systemsettings' and record['fields']['letterhead_logo']:
            raise ValidationError('Logo file paths cannot be imported. Export the image with BillTrack.')
    try:
        objects = list(serializers.deserialize('python', records))
        identities = {label: set() for label in MODEL_MAP}
        invoice_numbers = set()
        for item in objects:
            obj = item.object
            obj.full_clean(exclude=[field.name for field in obj._meta.fields if field.is_relation]
                           + ['letterhead_logo'], validate_unique=False, validate_constraints=False)
            identity = ((obj.tenant_id, obj.year, obj.month) if isinstance(obj, Bill)
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
