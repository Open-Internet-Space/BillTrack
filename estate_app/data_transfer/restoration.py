import uuid
from pathlib import Path
from django.core.exceptions import ValidationError
from ..models import Bill, Payment, SystemSettings, Tenant
from .serialization import MODELS


def restore_data(objects, logo, mode):
    """Caller owns the transaction. Raw saves preserve historical monetary fields/dates."""
    if mode == 'replace':
        Payment.objects.all().delete()
        Bill.objects.all().delete()
        Tenant.objects.all().delete()
        SystemSettings.objects.all().delete()
    maps = {model: {} for model in MODELS}
    counts = {'added': 0, 'kept': 0}
    updated_bills = set()
    existing_bills = set()
    saved_logo = None
    storage = SystemSettings._meta.get_field('letterhead_logo').storage
    try:
        for model in MODELS:
            for item in objects:
                obj = item.object
                if type(obj) is not model:
                    continue
                source_pk = obj.pk
                if model is Bill:
                    obj.tenant_id = maps[Tenant][obj.tenant_id]
                    existing = Bill.objects.filter(tenant_id=obj.tenant_id, year=obj.year, month=obj.month).first()
                elif model is Payment:
                    obj.bill_id = maps[Bill][obj.bill_id]
                    existing = Payment.objects.filter(uuid=obj.uuid).first()
                    if existing and existing.bill_id != obj.bill_id:
                        raise ValidationError('A payment UUID belongs to a different local bill. No records were imported.')
                elif model is Tenant:
                    existing = Tenant.objects.filter(uuid=obj.uuid).first()
                else:
                    existing = SystemSettings.objects.first()
                if existing:
                    maps[model][source_pk] = existing.pk
                    counts['kept'] += 1
                    if model is Bill:
                        existing_bills.add(existing.pk)
                    continue
                obj.pk = 1 if model is SystemSettings else None
                if model is SystemSettings and logo:
                    saved_logo = storage.save(f'invoice-branding/import-{uuid.uuid4().hex}{Path(logo.name).suffix.lower()}', logo)
                    obj.letterhead_logo = saved_logo
                # Fixture-style save bypasses automatic GST/date/penalty recalculation.
                item.save()
                maps[model][source_pk] = obj.pk
                counts['added'] += 1
                if model is Payment and obj.bill_id in existing_bills:
                    updated_bills.add(obj.bill_id)
        if mode == 'merge':
            for bill in Bill.objects.filter(pk__in=updated_bills):
                bill.update_status()
    except Exception:
        if saved_logo:
            storage.delete(saved_logo)
        raise
    return counts
