import copy
import uuid
from pathlib import Path
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.serializers.base import DeserializedObject
from django.db import models,transaction
from django.db.models import F
from ..models import (Allotment,AllotmentRequirement,Bill,EstateCharge,EstateChargePayment,
                      Payment,RentRevision,SecurityMovement,SystemSettings,Tenant)
from .graph import validate_graph
from .serialization import MODELS


def bind_graph(records):
    users=set(User.objects.values_list('pk',flat=True))
    for model,rows in records.items():
        for obj in rows.values():
            for field in model._meta.fields:
                if field.is_relation and field.remote_field.model in records:
                    identity=getattr(obj,field.attname)
                    if identity is not None:
                        try:setattr(obj,field.name,records[field.remote_field.model][identity])
                        except KeyError:raise ValidationError('The final estate graph contains a missing record reference.')
                elif field.is_relation and field.remote_field.model is User:
                    identity=getattr(obj,field.attname)
                    if identity not in users and not (identity is None and field.null):
                        raise ValidationError('An attributed user changed or was removed. Review the import again.')


def plan_restore(objects,mode):
    if mode not in ('merge','replace'):raise ValidationError('Choose Merge or Replace.')
    incoming=copy.deepcopy(objects)
    records={model:{obj.pk:obj for obj in model.objects.order_by('pk')} if mode=='merge' else {} for model in MODELS}
    maps={model:{} for model in MODELS}
    additions=[];kept=0
    protected={Allotment:('shop_id','tenant_id','renewal_of_id'),
        AllotmentRequirement:('allotment_id',),RentRevision:('original_award_id','effective_date','rate'),
        EstateCharge:('allotment_id','kind'),Payment:('bill_id',),EstateChargePayment:('charge_id',),
        SecurityMovement:('original_award_id','kind','amount','effective_date','operation_id','applied_bill_id',
                          'applied_charge_id','recorded_by_id','reference','reason')}
    for model in MODELS:
        rows=[item.object for item in incoming if type(item.object) is model]
        if model is Allotment:rows.sort(key=lambda obj:(len(obj._lineage()),obj.pk))
        else:rows.sort(key=lambda obj:obj.pk)
        next_id=max([0,*records[model],*[obj.pk for obj in rows]])+1
        for obj in rows:
            source_id=obj.pk
            for field in model._meta.fields:
                if field.is_relation and field.remote_field.model in maps:
                    identity=getattr(obj,field.attname)
                    if identity is not None:
                        try:setattr(obj,field.attname,maps[field.remote_field.model][identity])
                        except KeyError:raise ValidationError('Import dependency order or renewal lineage is invalid.')
            existing=None
            if mode=='merge':
                for candidate in records[model].values():
                    if model is SystemSettings:existing=candidate;break
                    if model is Bill:
                        match=(candidate.tenant_id,candidate.allotment_id,candidate.year,candidate.month)==(obj.tenant_id,obj.allotment_id,obj.year,obj.month)
                    else:match=candidate.uuid==obj.uuid
                    if match:existing=candidate;break
            if existing:
                fields=list(protected.get(model,()))
                if model in (Payment,EstateChargePayment) and (existing.source=='security_application' or obj.source=='security_application'):
                    fields+=['source','operation_id','amount','payment_date','recorded_by_id']
                    if model is Payment:fields+=['penalty_paid']
                if any(getattr(existing,key)!=getattr(obj,key) for key in fields):
                    raise ValidationError(f'{model._meta.verbose_name} identity conflicts with retained financial history.')
                if model is Bill and existing.invoice_no and obj.invoice_no and existing.invoice_no!=obj.invoice_no:
                    raise ValidationError('The retained billing period has a different invoice number.')
                maps[model][source_id]=existing.pk;kept+=1
                continue
            if model is SystemSettings:
                obj.pk = 1
            else:
                obj.pk = source_id if mode == 'replace' else next_id
            next_id+=1
            maps[model][source_id]=obj.pk
            records[model][obj.pk]=obj
            additions.append(obj)
    bind_graph(records)
    validate_graph([DeserializedObject(obj) for model in MODELS for obj in records[model].values()])
    numbers=[obj.invoice_no for obj in records[Bill].values() if obj.invoice_no]
    if len(numbers)!=len(set(numbers)):raise ValidationError('Conflicting invoice numbers in the final estate graph.')
    return additions,{'added':len(additions),'kept':kept}


def clear_business_records():
    # Reviewed whole-data replacement bypasses ordinary append-only deletion controls.
    for model in reversed(MODELS):
        if model is Allotment:
            terms=list(model.objects.all())
            terms.sort(key=lambda obj:len(obj._lineage()),reverse=True)
            for term in terms:models.QuerySet(model=model).filter(pk=term.pk).delete()
        else:models.QuerySet(model=model).all().delete()


@transaction.atomic
def restore_data(objects,logo,mode):
    """Validate the retained+incoming graph before writing historical records raw."""
    Tenant.objects.update(active=F('active'))
    additions,counts=plan_restore(objects,mode)
    saved_logo=None
    storage=SystemSettings._meta.get_field('letterhead_logo').storage
    try:
        if mode=='replace':clear_business_records()
        updated_bills=set()
        for obj in additions:
            if isinstance(obj,SystemSettings) and logo:
                saved_logo=storage.save(f'invoice-branding/import-{uuid.uuid4().hex}{Path(logo.name).suffix.lower()}',logo)
                obj.letterhead_logo=saved_logo
            DeserializedObject(obj).save()
            if isinstance(obj,Payment):updated_bills.add(obj.bill_id)
        if mode=='merge':
            new_bills={obj.pk for obj in additions if isinstance(obj,Bill)}
            for bill in Bill.objects.filter(pk__in=updated_bills-new_bills):bill.update_status()
    except Exception:
        if saved_logo:storage.delete(saved_logo)
        raise
    return counts
