"""Assessed charges, receipts and reviewed superuser financial decisions."""
from decimal import Decimal
import hashlib
import json
import uuid

from django.core import signing
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import filters, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..activity.api import AuditedViewSetMixin
from ..activity.context import operation
from ..models import EstateCharge, EstateChargePayment, UserProfile


def charge_queryset():
    return EstateCharge.objects.select_related('allotment__shop', 'allotment__tenant', 'waived_by', 'created_by').annotate(
        _amount_paid=Coalesce(Sum('payments__amount'), Value(0), output_field=DecimalField(max_digits=12,decimal_places=2))
    ).prefetch_related('payments__recorded_by')


def may_delete_charge(user, charge):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.pk == charge.created_by_id:
        return True
    try:
        return user.profile.role == 'admin'
    except UserProfile.DoesNotExist:
        return False


def charge_has_financial_history(charge):
    return bool(charge.amount_paid or charge.renewal_term_id or charge.last_operation_id or charge.waiver_amount)


class ChargePaymentSerializer(serializers.ModelSerializer):
    register_label=serializers.CharField(source='charge.allotment.register_label',read_only=True)
    tenant_name=serializers.CharField(source='charge.allotment.tenant.name',read_only=True)
    recorded_by_name=serializers.SerializerMethodField()

    def get_recorded_by_name(self,obj):
        return (obj.recorded_by.get_full_name() or obj.recorded_by.username) if obj.recorded_by_id else ''

    class Meta:
        model=EstateChargePayment
        fields='__all__'
        read_only_fields=['uuid','source','operation_id','recorded_by','created_at','updated_at']

    def validate(self,attrs):
        if self.initial_data.get('source','receipt')!='receipt':
            raise ValidationError({'source':'Use the reviewed security application action for a paired settlement.'})
        return attrs

    def create(self,validated_data):
        validated_data['recorded_by']=self.context['request'].user
        return super().create(validated_data)


class EstateChargeSerializer(serializers.ModelSerializer):
    register_label=serializers.CharField(source='allotment.register_label',read_only=True)
    tenant_name=serializers.CharField(source='allotment.tenant.name',read_only=True)
    tenant=serializers.IntegerField(source='allotment.tenant_id',read_only=True)
    gross_amount=serializers.DecimalField(max_digits=12,decimal_places=2,read_only=True)
    amount_paid=serializers.DecimalField(max_digits=12,decimal_places=2,read_only=True)
    balance_due=serializers.DecimalField(max_digits=12,decimal_places=2,read_only=True)
    status=serializers.CharField(read_only=True)
    overdue=serializers.BooleanField(read_only=True)
    payments=ChargePaymentSerializer(many=True,read_only=True)
    created_by_name=serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    def get_can_delete(self, obj):
        request = self.context.get('request')
        return bool(request and may_delete_charge(request.user, obj) and not charge_has_financial_history(obj))

    def get_created_by_name(self,obj):
        return (obj.created_by.get_full_name() or obj.created_by.username) if obj.created_by_id else ''

    class Meta:
        model=EstateCharge
        fields='__all__'
        read_only_fields=['uuid','renewal_term','waiver_amount','waiver_reference','waiver_reason','waived_by',
                          'waived_at','last_operation_id','created_by','created_at','updated_at']

    def create(self,validated_data):
        validated_data['created_by']=self.context['request'].user
        return super().create(validated_data)

    def validate(self,attrs):
        if any(key in self.initial_data for key in ('waiver_amount','waiver_reference','waiver_reason',
                                                   'waived_by','waived_at','last_operation_id')):
            raise ValidationError('Use the reviewed superuser decision action for waivers.')
        return attrs


class ChargeDecisionInput(serializers.Serializer):
    action=serializers.ChoiceField(choices=['waiver','assessment'])
    waiver_amount=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=Decimal('0'),required=False)
    net_amount=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=Decimal('0'),required=False)
    tax_amount=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=Decimal('0'),required=False)
    reference=serializers.CharField(max_length=250)
    reason=serializers.CharField(max_length=2000)

    def validate(self,attrs):
        required=['waiver_amount'] if attrs['action']=='waiver' else ['net_amount','tax_amount']
        for key in required:
            if key not in attrs:
                raise ValidationError({key:'Enter the reviewed amount explicitly, including zero.'})
        return attrs


class ChargeConfirmationInput(serializers.Serializer):
    confirmation=serializers.CharField(max_length=8192)


def charge_fingerprint(charge):
    state={key:str(getattr(charge,key)) for key in ('uuid','allotment_id','kind','net_amount','tax_amount',
        'waiver_amount','waiver_reference','waiver_reason','waived_by_id','waived_at','last_operation_id','updated_at',
        'authority_reference','description','assessed_on','due_date','renewal_term_id')}
    state['payments']=list(charge.payments.order_by('pk').values('uuid','amount','payment_date','receipt_reference','source','operation_id','updated_at'))
    return hashlib.sha256(json.dumps(state,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def prepare_charge_decision(charge,data,actor,operation_id):
    charge._decision_actor=actor
    charge._decision_reason=data['reason']
    charge.last_operation_id=operation_id
    if data['action']=='waiver':
        charge.waiver_amount=data['waiver_amount']
        charge.waiver_reference=data['reference']
        charge.waiver_reason=data['reason']
        charge.waived_by=actor
        charge.waived_at=timezone.now()
    else:
        charge.net_amount=data['net_amount']
        charge.tax_amount=data['tax_amount']
        charge.authority_reference=data['reference']
    charge.full_clean()


class EstateChargeViewSet(AuditedViewSetMixin,viewsets.ModelViewSet):
    queryset=EstateCharge.objects.all()
    serializer_class=EstateChargeSerializer
    permission_classes=[IsAuthenticated]
    filter_backends=[DjangoFilterBackend,filters.SearchFilter,filters.OrderingFilter]
    filterset_fields=['allotment','allotment__shop','allotment__tenant','kind']
    search_fields=['allotment__shop__code','allotment__tenant__name','authority_reference','description']
    ordering_fields=['due_date','assessed_on','created_at']
    ordering=['due_date','pk']

    def get_queryset(self):
        return charge_queryset()

    def get_deletion_plan(self):
        charge = self.get_object()
        if not may_delete_charge(self.request.user, charge):
            raise PermissionDenied('Only the person who recorded this charge or an administrator may delete it.')
        if charge_has_financial_history(charge):
            raise ValidationError('Charges with receipts, reviewed decisions or linked renewals are retained. Use the reviewed correction workflow.')
        return super().get_deletion_plan()

    @action(detail=True,methods=['post'],url_path='decision-preview')
    def decision_preview(self,request,pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied('Only a superuser may review financial assessment or waiver decisions.')
        serializer=ChargeDecisionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        charge=self.get_object()
        fingerprint=charge_fingerprint(charge)
        before=EstateChargeSerializer(charge,context={'request':request}).data
        operation_id=uuid.uuid4()
        data=serializer.validated_data
        prepare_charge_decision(charge,data,request.user,operation_id)
        payload={'charge':charge.pk,'uuid':str(charge.uuid),'actor':request.user.pk,'before':fingerprint,
                 'operation':str(operation_id),'data':{key:str(value) if isinstance(value,Decimal) else value for key,value in data.items()}}
        return Response({'before':before,'after':EstateChargeSerializer(charge,context={'request':request}).data,
            'confirmation':signing.dumps(payload,salt='estate-charge-decision',compress=True),'expires_in_seconds':600})

    @action(detail=True,methods=['post'],url_path='apply-decision')
    def apply_decision(self,request,pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied('Only a superuser may confirm a financial decision.')
        confirmation=ChargeConfirmationInput(data=request.data)
        confirmation.is_valid(raise_exception=True)
        try:
            payload=signing.loads(confirmation.validated_data['confirmation'],salt='estate-charge-decision',max_age=600)
        except (signing.BadSignature,TypeError,ValueError):
            raise ValidationError({'confirmation':'Preview the current charge decision again.'})
        if payload['actor']!=request.user.pk:
            raise PermissionDenied('This preview belongs to a different reviewer.')
        if str(payload['charge'])!=str(pk):
            raise ValidationError('The preview is for a different assessed obligation.')
        EstateCharge.objects.filter(pk=pk).update(description=F('description'))
        charge=self.get_object()
        if str(charge.uuid)!=payload['uuid']:
            raise ValidationError('The assessed obligation has changed. Preview again.')
        if str(charge.last_operation_id)==payload['operation']:
            return Response({'charge':EstateChargeSerializer(charge,context={'request':request}).data,'already_applied':True})
        if charge_fingerprint(charge)!=payload['before']:
            raise ValidationError('The assessment or its receipts changed. Preview the current balance again.')
        serializer=ChargeDecisionInput(data=payload['data'])
        serializer.is_valid(raise_exception=True)
        data=serializer.validated_data
        with operation(actor=request.user,source='api',reason=data['reason']):
            prepare_charge_decision(charge,data,request.user,payload['operation'])
            charge.save()
        return Response({'charge':EstateChargeSerializer(charge,context={'request':request}).data,'already_applied':False})


class ChargePaymentViewSet(AuditedViewSetMixin,viewsets.ModelViewSet):
    queryset=EstateChargePayment.objects.select_related('charge__allotment__shop','charge__allotment__tenant','recorded_by')
    serializer_class=ChargePaymentSerializer
    permission_classes=[IsAuthenticated]
    filter_backends=[DjangoFilterBackend,filters.SearchFilter,filters.OrderingFilter]
    filterset_fields=['charge','charge__allotment','source']
    search_fields=['charge__allotment__shop__code','charge__allotment__tenant__name','receipt_reference']
    ordering_fields=['payment_date','created_at']
    ordering=['-payment_date','-pk']

    def destroy(self,request,*args,**kwargs):
        try:
            admin=request.user.profile.role=='admin'
        except UserProfile.DoesNotExist:
            admin=False
        if not request.user.is_superuser and not admin:
            raise PermissionDenied('Only an administrator can delete a receipt after review.')
        if self.get_object().source!='receipt':
            raise ValidationError('Paired security settlements cannot be deleted as ordinary receipts.')
        return super().destroy(request,*args,**kwargs)
