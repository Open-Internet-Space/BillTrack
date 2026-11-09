"""
BillTrack - API Serializers
Returns ALL calculated data. React just displays it.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from .models import UserProfile, Tenant, Bill, Payment, SystemSettings


# ── User ──────────────────────────────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role']

    def get_role(self, obj):
        try:
            return obj.profile.role
        except UserProfile.DoesNotExist:
            return 'staff'


# ── Tenant ────────────────────────────────────────────────────────────────────
class TenantSerializer(serializers.ModelSerializer):
    last_billed_month = serializers.ReadOnlyField()
    custom_penalty_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    custom_penalty_lumpsum = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def to_internal_value(self, data):
        # Admin forms often send empty strings for optional numeric fields.
        # Convert those to null before DRF type conversion.
        data = data.copy()
        for field in ['custom_penalty_rate', 'custom_penalty_lumpsum']:
            if data.get(field) == '':
                data[field] = None
        return super().to_internal_value(data)

    class Meta:
        model = Tenant
        fields = ['id', 'uuid', 'name', 'type', 'contact', 'contact_not_provided',
                  'email', 'email_not_provided', 'gstin', 'gstin_not_provided',
                  'address', 'address_not_provided', 'active',
                  'due_days', 'penalty_type', 'custom_penalty_rate', 'custom_penalty_lumpsum',
                  'custom_penalty_frequency',
                  'created_at', 'updated_at', 'last_billed_month']
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']

    def validate(self, attrs):
        for field in ['custom_penalty_rate', 'custom_penalty_lumpsum']:
            if attrs.get(field) == '':
                attrs[field] = None
        if attrs.get('penalty_type') == 'system':
            if attrs.get('custom_penalty_rate') is not None:
                attrs['penalty_type'] = 'percentage'
            elif attrs.get('custom_penalty_lumpsum') is not None:
                attrs['penalty_type'] = 'lumpsum'
        return attrs


# ── Payment (for nested display) ──────────────────────────────────────────────
class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()
    bill_invoice = serializers.CharField(source='bill.invoice_no', read_only=True)
    bill_tenant = serializers.IntegerField(source='bill.tenant_id', read_only=True)
    bill_tenant_name = serializers.CharField(source='bill.tenant.name', read_only=True)
    bill_year = serializers.IntegerField(source='bill.year', read_only=True)
    bill_month = serializers.IntegerField(source='bill.month', read_only=True)
    bill_period = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ['id', 'bill', 'bill_invoice', 'bill_tenant', 'bill_tenant_name', 'bill_year', 'bill_month', 'bill_period', 'amount', 'payment_date',
                  'penalty_paid', 'receipt_no', 'notes',
                  'recorded_by', 'recorded_by_name', 'created_at']
        read_only_fields = ['id', 'recorded_by', 'created_at']

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return None

    def get_bill_period(self, obj):
        return f"{obj.bill.get_month_name()} {obj.bill.year}"

    def validate(self, attrs):
        amount = attrs.get('amount', getattr(self.instance, 'amount', 0))
        penalty_paid = attrs.get('penalty_paid', getattr(self.instance, 'penalty_paid', 0))
        if amount < 0 or (amount == 0 and penalty_paid == 0):
            raise serializers.ValidationError({'amount': 'Enter a principal or penalty payment'})
        if penalty_paid < 0:
            raise serializers.ValidationError({'penalty_paid': 'Penalty cannot be negative'})
        return attrs

    def create(self, validated_data):
        # Backend sets recorded_by automatically
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)


# ── Bill (with ALL calculated fields) ─────────────────────────────────────────
class BillSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        # Share settings within this response, never across requests.
        if '_penalty_settings' not in self.context:
            self.context['_penalty_settings'] = SystemSettings.get_settings()
        instance._penalty_config = instance.tenant.get_penalty_config(self.context['_penalty_settings'])
        return super().to_representation(instance)

    # Tenant info (read-only)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    tenant_type = serializers.CharField(source='tenant.type', read_only=True)
    tenant_due_days = serializers.IntegerField(source='tenant.due_days', read_only=True)
    
    # GST fields (ALL backend-generated)
    gst_on_rent     = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    cgst_on_rent    = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    sgst_on_rent    = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    igst_on_rent    = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    rent_with_gst   = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    # Calculated amounts (ALL backend-generated, React NEVER calculates these)
    total_amount    = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    amount_paid     = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    penalty_paid    = serializers.SerializerMethodField()
    balance_due     = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    previous_balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    previous_penalty = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    penalty         = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_payable   = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    days_overdue    = serializers.IntegerField(read_only=True)
    penalty_start_date = serializers.DateField(read_only=True)
    penalty_calculation = serializers.ReadOnlyField()
    receipt_status = serializers.CharField(read_only=True)
    
    # Month name (helper for display)
    month_name = serializers.SerializerMethodField()
    
    # Metadata
    created_by_name = serializers.SerializerMethodField()
    
    # Payments (nested)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Bill
        fields = [
            'id', 'invoice_no', 'tenant', 'tenant_name', 'tenant_type', 'tenant_due_days',
            'month', 'month_name', 'year',
            'rent', 'electric', 'electric_reading', 'water', 'gst_treatment',
            'gst_on_rent', 'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent', 'rent_with_gst',
            'total_amount', 'dispatch_ref_no', 'issue_date', 'due_date', 'status', 'receipt_status',
            'amount_paid', 'penalty_paid', 'balance_due', 'previous_balance', 'previous_penalty',
            'penalty', 'total_payable', 'days_overdue', 'penalty_start_date', 'penalty_calculation',
            'notes', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'payments',
        ]
        read_only_fields = ['id', 'status', 'created_by', 'created_at', 'updated_at',
                           'gst_on_rent', 'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent']
        extra_kwargs = {'due_date': {'required': False}}

    def validate_issue_date(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError('Confirmed receipt date cannot be in the future.')
        return value

    def get_month_name(self, obj):
        return obj.get_month_name()

    def get_penalty_paid(self, obj):
        total = getattr(obj, '_penalty_paid_total', None)
        if total is None:
            total = obj.payments.aggregate(total=Sum('penalty_paid'))['total'] or 0
        return total

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def create(self, validated_data):
        # Backend sets created_by automatically
        validated_data['created_by'] = self.context['request'].user
        # Keep invoice generation backend-owned; blank/None both mean "generate".
        if not validated_data.get('invoice_no'):
            validated_data['invoice_no'] = None
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'invoice_no' in validated_data and not validated_data.get('invoice_no'):
            validated_data['invoice_no'] = None
        return super().update(instance, validated_data)


class BillListSerializer(BillSerializer):
    """Lighter version for list view (no nested payments)"""
    class Meta(BillSerializer.Meta):
        fields = [
            f for f in BillSerializer.Meta.fields
            if f not in {'payments', 'previous_balance', 'previous_penalty', 'total_payable'}
        ]
