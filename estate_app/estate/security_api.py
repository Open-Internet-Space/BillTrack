"""Security receipt history and signed superuser decisions; no bank transfers."""
from decimal import Decimal
import hashlib
import json
import uuid

from django.core import signing
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..activity.api import AuditedViewSetMixin
from ..activity.context import operation
from ..models import Allotment, AllotmentRequirement, Bill, EstateCharge, EstateChargePayment, Payment, SecurityMovement, SystemSettings, Tenant
from .charges import charge_queryset
from .security import required_security


class SecurityMovementSerializer(serializers.ModelSerializer):
    shop_code = serializers.CharField(source='original_award.shop.code',read_only=True)
    tenant_name = serializers.CharField(source='original_award.tenant.name',read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.username',read_only=True)

    class Meta:
        model = SecurityMovement
        fields = '__all__'
        read_only_fields = ['uuid','kind','operation_id','applied_bill','applied_charge','recorded_by','created_at']

    def validate(self,attrs):
        if self.initial_data.get('kind','received') != 'received' or any(
                self.initial_data.get(key) for key in ('operation_id','applied_bill','applied_charge')):
            raise ValidationError('Use the reviewed security decision action for a debit or application.')
        return attrs

    def create(self,validated_data):
        return SecurityMovement.objects.create(**validated_data,kind='received',recorded_by=self.context['request'].user)


class SecurityMovementViewSet(AuditedViewSetMixin,mixins.CreateModelMixin,viewsets.ReadOnlyModelViewSet):
    queryset = SecurityMovement.objects.select_related('original_award__shop','original_award__tenant','recorded_by')
    serializer_class = SecurityMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,filters.SearchFilter,filters.OrderingFilter]
    filterset_fields = ['original_award','kind']
    search_fields = ['original_award__shop__code','original_award__tenant__name','reference']
    ordering_fields = ['effective_date','created_at']
    ordering = ['effective_date','pk']

    def get_deletion_plan(self):
        raise ValidationError('Security movements are retained financial history.')


def security_summary(root):
    movements = list(root.security_movements.select_related('original_award__shop','original_award__tenant','recorded_by'))
    totals = {kind:sum((row.amount for row in movements if row.kind==kind),Decimal('0'))
              for kind in ('received','refunded','applied','forfeited')}
    held = totals['received']-totals['refunded']-totals['applied']-totals['forfeited']
    outstanding = max(Decimal('0'),(root.security_required_amount or Decimal('0'))-totals['received'])
    due = root.security_effective_due_date
    return {'id':root.pk,'uuid':str(root.uuid),'shop_code':root.shop.code,'tenant':root.tenant_id,
        'tenant_name':root.tenant.name,'award_reference':root.award_reference,
        'initial_monthly_rent':f'{root.security_initial_rent:.2f}' if root.security_initial_rent is not None else None,
        'required_amount':f'{root.security_required_amount:.2f}' if root.security_required_amount is not None else None,
        'due_date':root.security_due_date.isoformat() if root.security_due_date else None,
        'extended_due_date':root.security_extended_due_date.isoformat() if root.security_extended_due_date else None,
        'extension_reference':root.security_extension_reference,
        'requirement_reference':root.security_requirement_reference,'requirement_reason':root.security_requirement_reason,
        'effective_due_date':due.isoformat() if due else None,
        'outstanding_requirement':f'{outstanding:.2f}','deposit_overdue':bool(due and due<timezone.localdate() and outstanding),
        'held':f'{held:.2f}',**{key:f'{value:.2f}' for key,value in totals.items()},
        'refund_review_due':root.security_refund_review_due.isoformat(),'refund_review_status':root.refund_review_status,
        'refund_review_reference':root.refund_review_reference,'refund_review_reason':root.refund_review_reason,
        'as_of':timezone.localdate().isoformat(),'movements':SecurityMovementSerializer(movements,many=True).data}


def refund_issues(root):
    from ..views.bills import bill_read_queryset
    issues = []
    latest = root
    while getattr(latest,'renewal',None):
        latest = latest.renewal
    if latest.effective_end >= timezone.localdate():
        issues.append('The final approved term has not ended.')
    if not latest.handover_date:
        issues.append('Physical handover of the final term is not confirmed.')
    for award in Allotment.objects.filter(tenant_id=root.tenant_id,renewal_of__isnull=True,security_required_amount__isnull=False):
        if Decimal(security_summary(award)['outstanding_requirement'])>0:
            issues.append(f'Award {award.pk}: the reviewed security requirement is not fully received.')
    for bill in bill_read_queryset().filter(tenant_id=root.tenant_id):
        if bill.is_draft or bill.balance_due+bill.penalty>0:
            issues.append(f'Invoice {bill.invoice_no or bill.pk} is draft or has unresolved dues.')
    for charge in charge_queryset().filter(allotment__tenant_id=root.tenant_id):
        if charge.balance_due>0:
            issues.append(f'Charge {charge.pk} ({charge.allotment.shop.code}) has unresolved dues.')
    for item in AllotmentRequirement.objects.filter(allotment__tenant_id=root.tenant_id,applicable=True,verified_on__isnull=True):
        issues.append(f'Term {item.allotment_id}: {item.get_kind_display()} remains unverified.')
    for item in AllotmentRequirement.objects.filter(allotment__tenant_id=root.tenant_id,applicable=True,
                                                   verified_on__isnull=False).exclude(unresolved_issue=''):
        issues.append(f'Term {item.allotment_id}: {item.unresolved_issue}')
    return issues


def security_fingerprint(root):
    terms = Allotment.objects.filter(tenant_id=root.tenant_id)
    bills = Bill.objects.filter(tenant_id=root.tenant_id)
    charges = EstateCharge.objects.filter(allotment__tenant_id=root.tenant_id)
    state = {'root':str(root.uuid),'as_of':timezone.localdate().isoformat(),
        'terms':list(terms.order_by('pk').values()),
        'requirements':list(AllotmentRequirement.objects.filter(allotment__in=terms).order_by('pk').values()),
        'bills':list(bills.order_by('pk').values()),
        'payments':list(Payment.objects.filter(bill__in=bills).order_by('pk').values()),
        'charges':list(charges.order_by('pk').values()),
        'charge_payments':list(EstateChargePayment.objects.filter(charge__in=charges).order_by('pk').values()),
        'movements':list(root.security_movements.order_by('pk').values()),
        'tenant_policy':list(Tenant.objects.filter(pk=root.tenant_id).values('uuid','due_days','penalty_type',
            'custom_penalty_rate','custom_penalty_lumpsum','custom_penalty_frequency')),
        'settings':list(SystemSettings.objects.order_by('pk').values())}
    return hashlib.sha256(json.dumps(state,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


class SecurityDecisionInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=['requirement','apply_bill','apply_charge','refund','forfeit'])
    reference = serializers.CharField(max_length=250)
    reason = serializers.CharField(max_length=2000)
    initial_monthly_rent = serializers.DecimalField(max_digits=10,decimal_places=2,min_value=Decimal('0.01'),required=False)
    required_amount = serializers.DecimalField(max_digits=10,decimal_places=2,min_value=Decimal('0.01'),required=False)
    extended_due_date = serializers.DateField(required=False,allow_null=True)
    extension_reference = serializers.CharField(max_length=250,required=False,allow_blank=True)
    amount = serializers.DecimalField(max_digits=10,decimal_places=2,min_value=Decimal('0.01'),required=False)
    interest_amount = serializers.DecimalField(max_digits=10,decimal_places=2,min_value=Decimal('0'),default=Decimal('0'))
    effective_date = serializers.DateField(required=False)
    bill = serializers.IntegerField(min_value=1,required=False)
    charge = serializers.IntegerField(min_value=1,required=False)
    exception_reference = serializers.CharField(max_length=250,required=False,allow_blank=True)

    def validate(self,attrs):
        required = ['initial_monthly_rent'] if attrs['action']=='requirement' else ['amount','effective_date']
        required += {'apply_bill':['bill'],'apply_charge':['charge']}.get(attrs['action'],[])
        for key in required:
            if key not in attrs:
                raise ValidationError({key:'Enter the actual reviewed value.'})
        if attrs['action']!='apply_bill' and attrs['interest_amount']:
            raise ValidationError('Only a bill application can include an explicit interest component.')
        return attrs


class SecurityConfirmationInput(serializers.Serializer):
    confirmation = serializers.CharField(max_length=8192)


def prepare_security_decision(root,data,actor,operation_id):
    root._security_actor,root._security_reason = actor,data['reason']
    before = security_summary(root)
    movement = receipt = None
    issues = []
    if data['action']=='requirement':
        root.security_initial_rent = data['initial_monthly_rent']
        root.security_required_amount = data.get('required_amount',required_security(data['initial_monthly_rent']))
        root.security_requirement_reference,root.security_requirement_reason = data['reference'],data['reason']
        root.security_extended_due_date = data.get('extended_due_date')
        root.security_extension_reference = data.get('extension_reference','')
        root.refund_review_status,root.refund_review_reference,root.refund_review_reason = 'pending','',''
        root.security_last_operation_id = operation_id
        root.full_clean()
    else:
        movement = SecurityMovement(original_award=root,kind={'refund':'refunded','forfeit':'forfeited'}.get(data['action'],'applied'),
            amount=data['amount'],effective_date=data['effective_date'],reference=data['reference'],reason=data['reason'],
            recorded_by=actor,operation_id=operation_id)
        movement._security_authorized = True
        if data['action']=='refund':
            if root.security_required_amount is None:
                raise ValidationError('Record the reviewed security requirement before refund clearance.')
            issues = refund_issues(root)
            exception = data.get('exception_reference','')
            if issues and not exception:
                raise ValidationError({'clearance':issues,'exception_reference':'An explicit authorized exception is required to refund with unresolved matters.'})
            root.refund_review_status = 'exception' if exception else 'cleared'
            root.refund_review_reference = exception or data['reference']
            root.refund_review_reason = data['reason']
            root.full_clean()
            if exception:
                movement.reason += '\nAuthorized exception: '+exception
        elif data['action']=='apply_bill':
            from ..views.bills import bill_read_queryset
            bill = get_object_or_404(bill_read_queryset(),pk=data['bill'])
            interest = data['interest_amount']
            principal = data['amount']-interest
            if principal<0 or principal>bill.balance_due or interest>bill.penalty:
                raise ValidationError('Review principal and interest separately; neither component may exceed the current balance.')
            movement.applied_bill = bill
            receipt = Payment(bill=bill,amount=principal,penalty_paid=interest,payment_date=data['effective_date'],
                source='security_application',operation_id=operation_id,recorded_by=actor,
                receipt_no=f'Security {operation_id}',notes=data['reference']+'\n'+data['reason'])
        elif data['action']=='apply_charge':
            charge = get_object_or_404(charge_queryset(),pk=data['charge'])
            movement.applied_charge = charge
            receipt = EstateChargePayment(charge=charge,amount=data['amount'],payment_date=data['effective_date'],
                source='security_application',operation_id=operation_id,recorded_by=actor,
                receipt_reference=data['reference'],notes=data['reason'])
        movement.full_clean()
        if receipt:
            receipt._security_authorized = True
            receipt._security_movement = movement
            receipt.full_clean()
    after = security_summary(root)
    if movement:
        after['held'] = f"{Decimal(before['held'])-movement.amount:.2f}"
        after[movement.kind] = f"{Decimal(before[movement.kind])+movement.amount:.2f}"
    settlement = None
    if receipt:
        target = receipt.bill if isinstance(receipt,Payment) else receipt.charge
        interest = receipt.penalty_paid if isinstance(receipt,Payment) else Decimal('0')
        settlement = {'target':target.pk,'shop_code':target.allotment.shop.code,
            'label':target.invoice_no if isinstance(receipt,Payment) else target.authority_reference,
            'principal_applied':f'{receipt.amount:.2f}','interest_applied':f'{interest:.2f}',
            'principal_remaining':f'{target.balance_due-receipt.amount:.2f}'}
    return {'before':before,'after':after,'clearance_issues':issues,'settlement':settlement},movement,receipt


class SecurityAccountSerializer(serializers.Serializer):
    def to_representation(self,instance):
        return security_summary(instance)


class SecurityAccountViewSet(AuditedViewSetMixin,viewsets.ReadOnlyModelViewSet):
    queryset = Allotment.objects.filter(renewal_of__isnull=True).select_related('shop','tenant')
    serializer_class = SecurityAccountSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self,request,*args,**kwargs):
        root = self.get_object()
        return Response({**security_summary(root),'clearance_issues':refund_issues(root)})

    def get_deletion_plan(self):
        raise ValidationError('Security belongs to protected original award history.')

    @action(detail=True,methods=['post'],url_path='decision-preview')
    def decision_preview(self,request,pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied('Only a superuser may review a security financial decision.')
        serializer = SecurityDecisionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        root = self.get_object()
        fingerprint = security_fingerprint(root)
        operation_id = uuid.uuid4()
        result,_,_ = prepare_security_decision(root,serializer.validated_data,request.user,operation_id)
        payload = {'root':root.pk,'uuid':str(root.uuid),'actor':request.user.pk,'before':fingerprint,
            'operation':str(operation_id),'data':json.loads(json.dumps(serializer.validated_data,default=str))}
        return Response({**result,'confirmation':signing.dumps(payload,salt='estate-security-decision',compress=True),
                         'expires_in_seconds':600})

    @action(detail=True,methods=['post'],url_path='apply-decision')
    def apply_decision(self,request,pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied('Only a superuser may confirm a security financial decision.')
        serializer = SecurityConfirmationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = signing.loads(serializer.validated_data['confirmation'],salt='estate-security-decision',max_age=600)
        except (signing.BadSignature,TypeError,ValueError):
            raise ValidationError('Preview the current security decision again.')
        if payload['actor']!=request.user.pk:
            raise PermissionDenied('This security preview belongs to another reviewer.')
        if str(payload['root'])!=str(pk):
            raise ValidationError('This preview belongs to another original award.')
        Allotment.objects.filter(pk=pk).update(actual_area=F('actual_area'))
        root = self.get_object()
        if str(root.uuid)!=payload['uuid']:
            raise ValidationError('The original award identity changed; preview again.')
        if str(root.security_last_operation_id)==payload['operation'] or root.security_movements.filter(operation_id=payload['operation']).exists():
            return Response({'account':security_summary(root),'already_applied':True})
        if security_fingerprint(root)!=payload['before']:
            raise ValidationError('Estate evidence or balances changed; preview the current decision again.')
        serializer = SecurityDecisionInput(data=payload['data'])
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with operation(actor=request.user,source='api',reason=data['reason']):
            _,movement,receipt = prepare_security_decision(root,data,request.user,payload['operation'])
            if data['action'] in ('requirement','refund'):
                root.save()
            if movement:
                movement.save()
            if receipt:
                receipt.save()
        return Response({'account':security_summary(root),'already_applied':False})
