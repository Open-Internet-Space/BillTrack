import hashlib
import json
from itertools import groupby
from django.contrib.admin.utils import NestedObjects
from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from .database import FIELDS, snapshot


def deletion_plan(objects, *, soft=False):
    objects = list(objects)
    collector = NestedObjects(using=objects[0]._state.db if objects else 'default')
    for _, group in groupby(objects, key=type):
        collector.collect(list(group))
    rows = []
    affected = []
    def add(model, instances, effect):
        label = model._meta.label_lower
        fields = FIELDS.get(label)
        instances = list(instances)
        if not fields:
            rows.append([effect, label, len(instances)])
            if instances:
                affected.append(f'{effect}: {len(instances)} {model._meta.verbose_name_plural} (managed security records)')
            return
        for obj in instances:
            from django.db.models.fields.files import FieldFile
            data = {field: str(getattr(obj, field)) if isinstance(getattr(obj, field), FieldFile)
                    else getattr(obj, field) for field in fields.split()}
            safe = snapshot(label, json.dumps(data, cls=DjangoJSONEncoder))
            rows.append([effect, label, str(obj.pk), safe])
            name = data.get('name') or data.get('allottee_name') or data.get('invoice_no') or data.get('username') or ''
            affected.append(f'{effect}: {model._meta.verbose_name} #{obj.pk} {name}')
    if soft:
        add(type(objects[0]), objects, 'Deactivate (billing history retained)')
    else:
        for model, instances in collector.data.items():
            add(model, instances, 'Delete')
        for (field, value), groups in collector.field_updates.items():
            for group in groups:
                add(field.model, group, f'Set {field.name} to {value}')
        from ..models import Bill, Payment
        if Payment in collector.data and Bill not in collector.data:
            bill_ids = {payment.bill_id for payment in collector.data[Payment]}
            add(Bill, Bill.objects.filter(pk__in=bill_ids), 'Recalculate status and balance')
    digest = hashlib.sha256(json.dumps(sorted(rows, key=str), cls=DjangoJSONEncoder).encode()).hexdigest()
    return {'affected': affected, 'digest': digest, 'protected': bool(collector.protected) and not soft,
            'confirmation': signing.dumps(digest, salt='billtrack-deletion')}


def confirmed(token, plan):
    try:
        return signing.loads(token, salt='billtrack-deletion', max_age=1800) == plan['digest']
    except (signing.BadSignature, TypeError):
        return False
