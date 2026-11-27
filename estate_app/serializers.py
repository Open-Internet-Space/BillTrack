"""
BillTrack - API Serializers
Returns ALL calculated data. React just displays it.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError as ModelValidationError
from decimal import Decimal
import calendar
import datetime
from .models import UserProfile, Tenant, Bill, Payment, SystemSettings


# ── User ──────────────────────────────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    premises_enabled = serializers.SerializerMethodField()
    allotment_details_enabled = serializers.SerializerMethodField()
    bill_email_copy_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'is_superuser', 'premises_enabled',
                  'allotment_details_enabled', 'bill_email_copy_enabled']
        read_only_fields = ['is_superuser']

    def get_premises_enabled(self, obj):
        return SystemSettings.premises_are_enabled()

    def get_bill_email_copy_enabled(self, obj):
        return SystemSettings.feature_enabled('bill_email_copy_enabled')

    def get_allotment_details_enabled(self, obj):
        return SystemSettings.feature_enabled('allotment_details_enabled')

    def get_role(self, obj):
        try:
            return obj.profile.role
        except UserProfile.DoesNotExist:
            return 'staff'


# ── Tenant ────────────────────────────────────────────────────────────────────
class TenantSerializer(serializers.ModelSerializer):
    last_billed_month = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
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
        fields = ['id', 'uuid', 'name', 'allotment_description', 'display_name', 'type', 'contact', 'contact_not_provided',
                  'email', 'email_not_provided', 'gstin', 'gstin_not_provided',
                  'address', 'address_not_provided', 'active',
                  'due_days', 'penalty_type', 'custom_penalty_rate', 'custom_penalty_lumpsum',
                  'custom_penalty_frequency',
                  'created_at', 'updated_at', 'last_billed_month', 'contract_draft']
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at', 'contract_draft']

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
    bill_tenant_display_name = serializers.CharField(source='bill.tenant.display_name', read_only=True)
    bill_allotment = serializers.IntegerField(source='bill.allotment_id', read_only=True, allow_null=True)
    bill_year = serializers.IntegerField(source='bill.year', read_only=True)
    bill_month = serializers.IntegerField(source='bill.month', read_only=True)
    bill_period = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ['id', 'bill', 'bill_invoice', 'bill_tenant', 'bill_tenant_name', 'bill_tenant_display_name', 'bill_allotment', 'bill_year', 'bill_month', 'bill_period', 'amount', 'payment_date',
                  'penalty_paid', 'receipt_no', 'notes', 'source', 'operation_id',
                  'recorded_by', 'recorded_by_name', 'created_at']
        read_only_fields = ['id', 'recorded_by', 'created_at', 'source', 'operation_id']

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return None

    def get_bill_period(self, obj):
        return f"{obj.bill.get_month_name()} {obj.bill.year}"

    def validate(self, attrs):
        if self.initial_data.get('source', 'receipt') != 'receipt' or self.initial_data.get('operation_id'):
            raise serializers.ValidationError('Use the reviewed security action for a paired settlement.')
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
    tenant_display_name = serializers.SerializerMethodField()
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
    deadline_established = serializers.BooleanField(read_only=True)
    is_draft = serializers.BooleanField(read_only=True)
    payment_days_overdue = serializers.IntegerField(read_only=True)
    # Month name (helper for display)
    month_name = serializers.SerializerMethodField()

    # Metadata
    created_by_name = serializers.SerializerMethodField()

    # Payments (nested)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Bill
        fields = [
            'id', 'invoice_no', 'tenant', 'tenant_name', 'tenant_display_name', 'tenant_type', 'tenant_due_days',
            'allotment', 'billing_category',
            'billing_policy', 'raised_date', 'email_dispatched_at', 'dispatch_recipient',
            'dispatch_message_reference', 'dispatch_sender', 'rent_revision', 'rate_snapshot', 'area_snapshot',
            'rent_revision_reference', 'rent_override_reason', 'rate_exception_reference',
            'month', 'month_name', 'year',
            'rent', 'electric', 'electric_reading', 'water', 'gst_treatment',
            'full_month_rent', 'holiday_start_date', 'holiday_end_date', 'holiday_closed_days', 'holiday_waiver',
            'gst_on_rent', 'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent', 'rent_with_gst',
            'total_amount', 'dispatch_ref_no', 'issue_date', 'due_date', 'status', 'receipt_status',
            'deadline_established', 'is_draft', 'payment_days_overdue',
            'amount_paid', 'penalty_paid', 'balance_due', 'previous_balance', 'previous_penalty',
            'penalty', 'total_payable', 'days_overdue', 'penalty_start_date', 'penalty_calculation',
            'notes', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'payments',
        ]
        read_only_fields = ['id', 'status', 'created_by', 'created_at', 'updated_at',
                           'dispatch_sender', 'rent_revision', 'rate_snapshot', 'area_snapshot', 'rent_revision_reference',
                           'holiday_closed_days', 'holiday_waiver',
                           'gst_on_rent', 'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent']
        # Installed DRF treats conditional uniqueness as unconditional; the database enforces both scopes.
        validators = []
        extra_kwargs = {'due_date': {'required': False}, 'allotment': {'required': False, 'allow_null': True}}

    def get_tenant_display_name(self, obj):
        return obj.tenant.display_name

    def validate(self, attrs):
        instance = self.instance
        if instance is None:
            category = attrs.setdefault('billing_category', 'allotment')
            if category == 'legacy':
                raise serializers.ValidationError({'billing_category': 'New bills cannot be created as legacy records.'})
        else:
            if any(field in attrs and attrs[field] != getattr(instance, field)
                   for field in ('tenant', 'allotment', 'billing_category', 'billing_policy')):
                raise serializers.ValidationError('Use the reviewed assignment workflow to change a bill owner, term or category.')
            category = attrs.get('billing_category', instance.billing_category)
        term = attrs.get('allotment', instance.allotment if instance else None)
        tenant = attrs.get('tenant', instance.tenant if instance else None)
        if (category == 'allotment') != bool(term):
            raise serializers.ValidationError({'allotment': 'Choose a term for allotment billing, or explicitly select other charges.'})
        if term and tenant and term.tenant_id != tenant.pk:
            raise serializers.ValidationError({'allotment': 'This term belongs to another allottee.'})
        if category == 'other' and not attrs.get('notes', instance.notes if instance else '').strip():
            raise serializers.ValidationError({'notes': 'Describe the reviewed other monthly charge.'})
        if instance is None:
            if tenant and not tenant.active:
                raise serializers.ValidationError({'tenant': 'Choose an active allottee.'})
            notice = term and term.notice_governed
            policy = 'notices_368_369' if notice else 'legacy_receipt'
            if attrs.get('billing_policy', policy) != policy:
                raise serializers.ValidationError({'billing_policy': 'The governing allotment determines the billing policy.'})
            attrs['billing_policy'] = policy
            if attrs.get('full_month_rent') is None and 'rent' in attrs:
                attrs['full_month_rent'] = attrs['rent']
            if policy == 'legacy_receipt' and not any(field in attrs for field in ('full_month_rent', 'rent')):
                if not term or not term.original_award.rent_revisions.exists():
                    raise serializers.ValidationError({'full_month_rent': 'Enter the reviewed full-month rent.'})
                from .estate.billing import rent_schedule
                try:
                    attrs['full_month_rent'] = rent_schedule(term, attrs['year'], attrs['month'])['full_month_rent']
                except ModelValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages) from exc
        if any(key in attrs and attrs[key] != getattr(instance, key, None)
               for key in ('email_dispatched_at', 'dispatch_recipient', 'dispatch_message_reference')):
            attrs['dispatch_sender'] = self.context['request'].user if attrs.get('email_dispatched_at', getattr(instance, 'email_dispatched_at', None)) else None
        candidate = Bill(**{field.attname: getattr(instance, field.attname) for field in Bill._meta.fields}) if instance else Bill()
        for field, value in attrs.items():
            setattr(candidate, field, value)
        finalizing = instance and instance.raised_date is None and candidate.raised_date is not None
        period_changed = instance and (instance.year,instance.month) != (candidate.year,candidate.month)
        if candidate.billing_policy == 'notices_368_369' and (finalizing or period_changed) and not candidate.rent_override_reason.strip():
            candidate.full_month_rent = None
        try:
            candidate.prepare_notice_rent(refresh=instance is None or finalizing or period_changed)
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        if candidate.billing_policy == 'notices_368_369':
            attrs.update({key: getattr(candidate, key) for key in ('full_month_rent', 'rate_snapshot', 'area_snapshot',
                'rent_revision_reference', 'rent_revision_id')})
        base = attrs.get('full_month_rent', instance.full_month_rent if instance else None)
        if base is None and instance and instance.full_month_rent is not None:
            raise serializers.ValidationError({'full_month_rent': 'Keep the original rent basis; clear both closure dates to remove a waiver.'})
        start = attrs.get('holiday_start_date', instance.holiday_start_date if instance else None)
        end = attrs.get('holiday_end_date', instance.holiday_end_date if instance else None)
        year, month = attrs.get('year', instance.year if instance else None), attrs.get('month', instance.month if instance else None)
        if base is not None:
            from .estate.billing import holiday_rent
            try:
                result = holiday_rent(base, year, month, start, end)
            except ModelValidationError as exc:
                raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
            if start and not result['closed_days'] and not self.context.get('allow_nonoverlap_holiday'):
                raise serializers.ValidationError({'holiday_start_date': 'This closure does not overlap the selected billing period.'})
            attrs['rent'] = result['applicable_rent']
        elif start or end:
            raise serializers.ValidationError({'full_month_rent': 'Record the original full-month rent for this waiver.'})
        for field, value in attrs.items():
            setattr(candidate, field, value)
        try:
            candidate.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        return attrs

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


class BillRangeSerializer(serializers.Serializer):
    from_month = serializers.IntegerField(min_value=1, max_value=12)
    to_month = serializers.IntegerField(min_value=1, max_value=12)
    from_year = serializers.IntegerField(min_value=2000, max_value=2100)
    to_year = serializers.IntegerField(min_value=2000, max_value=2100)
    month_items = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    def validate(self, attrs):
        start = attrs['from_year'] * 12 + attrs['from_month']
        end = attrs['to_year'] * 12 + attrs['to_month']
        if not 1 <= end - start + 1 <= 36:
            raise serializers.ValidationError('Choose an ordered range of at most 36 months.')
        items = {}
        for item in attrs['month_items']:
            try:
                year, month = int(item.get('year')), int(item.get('month'))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'month_items': 'Each electricity row needs a valid month and year.'})
            if not 1 <= month <= 12 or not start <= year * 12 + month <= end or (year, month) in items:
                raise serializers.ValidationError({'month_items': 'Electricity rows must be unique months within this range.'})
            items[(year, month)] = item
        common = {key: self.initial_data[key] for key in (
            'tenant', 'allotment', 'billing_category', 'rent', 'full_month_rent', 'water',
            'gst_treatment', 'notes', 'holiday_start_date', 'holiday_end_date', 'due_date',
            'raised_date', 'rent_override_reason', 'rate_exception_reference', 'billing_policy',
        ) if key in self.initial_data}
        rows = []
        for index in range(start, end + 1):
            year, month = (index - 1) // 12, (index - 1) % 12 + 1
            item = items.get((year, month), {})
            serializer = BillSerializer(data={**common, 'year': year, 'month': month,
                'electric': item.get('electric', self.initial_data.get('electric', 0)) or 0,
                'electric_reading': item.get('electric_reading', self.initial_data.get('electric_reading', '')) or '',
            }, context={**self.context, 'allow_nonoverlap_holiday': True})
            serializer.is_valid(raise_exception=True)
            rows.append(serializer)
        first = rows[0].validated_data
        holiday_start, holiday_end = first.get('holiday_start_date'), first.get('holiday_end_date')
        if holiday_start and (holiday_end < datetime.date(attrs['from_year'], attrs['from_month'], 1)
                or holiday_start > datetime.date(attrs['to_year'], attrs['to_month'],
                                                calendar.monthrange(attrs['to_year'], attrs['to_month'])[1])):
            raise serializers.ValidationError({'holiday_start_date': 'This closure does not overlap the billing range.'})
        attrs['bills'] = rows
        return attrs

    def save(self):
        from django.db import transaction
        created, skipped = [], []
        with transaction.atomic():
            for serializer in self.validated_data['bills']:
                values = serializer.validated_data
                if Bill.objects.filter(tenant=values['tenant'], allotment=values.get('allotment'),
                                       year=values['year'], month=values['month']).exists():
                    skipped.append({'year': values['year'], 'month': values['month'],
                                    'month_name': calendar.month_abbr[values['month']], 'reason': 'Already exists'})
                else:
                    created.append(serializer.save())
        return created, skipped
