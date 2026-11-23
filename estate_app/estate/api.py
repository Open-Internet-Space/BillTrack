import datetime as dt
from decimal import Decimal
from django.core.exceptions import ValidationError as ModelValidationError

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, serializers, viewsets
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from ..activity.api import AuditedViewSetMixin
from ..models import Allotment, AllotmentRequirement, RentRevision, Shop
from .security import SECURITY_FIELDS


class ShopSerializer(serializers.ModelSerializer):
    occupancy_status = serializers.ReadOnlyField()

    class Meta:
        model = Shop
        fields = '__all__'


class AllotmentSerializer(serializers.ModelSerializer):
    total_due = serializers.SerializerMethodField()

    shop_code = serializers.CharField(source='shop.code', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    effective_end = serializers.ReadOnlyField()
    vacation_due_date = serializers.ReadOnlyField()
    status = serializers.ReadOnlyField()
    extension_number = serializers.ReadOnlyField()
    original_award_id = serializers.SerializerMethodField()
    notice_governed = serializers.BooleanField(read_only=True)
    renewal_fee_settled = serializers.SerializerMethodField()
    renewal_fee_charge_id = serializers.SerializerMethodField()

    def get_total_due(self, obj):
        monthly = sum((bill.balance_due + bill.penalty for bill in obj.bills.all() if not bill.is_draft), Decimal('0'))
        charges = sum(charge.balance_due for charge in obj.charges.all())
        return f'{monthly + charges:.2f}'

    class Meta:
        model = Allotment
        fields = '__all__'
        read_only_fields = list(SECURITY_FIELDS)

    def get_original_award_id(self, obj):
        return obj.original_award.pk

    def get_renewal_fee_charge_id(self, obj):
        return next((charge.pk for charge in obj.charges.all() if charge.kind == 'extension_fee'), None)

    def get_renewal_fee_settled(self, obj):
        return not obj.notice_governed or any(
            charge.kind == 'extension_fee' and charge.balance_due == 0 for charge in obj.charges.all())


class RequirementSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()
    shop_code = serializers.CharField(source='allotment.shop.code', read_only=True)
    tenant_name = serializers.CharField(source='allotment.tenant.name', read_only=True)

    class Meta:
        model = AllotmentRequirement
        fields = '__all__'
        read_only_fields = ['verified_by']

    def validate(self, attrs):
        if 'verified_on' in attrs:
            attrs['verified_by'] = self.context['request'].user if attrs['verified_on'] else None
        return attrs


class EstateViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

class ShopViewSet(EstateViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    search_fields = ['code', 'name', 'location', 'authorized_services', 'allotments__tenant__name']
    filterset_fields = ['category', 'space_type', 'active']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['code']


def allotment_queryset():
    return Allotment.objects.select_related('shop', 'tenant', 'renewal_of', 'renewal_of__renewal_of',
                                             'renewal', 'renewal__renewal').prefetch_related('charges__payments', 'bills__payments')


class AllotmentViewSet(EstateViewSet):
    queryset = allotment_queryset()
    serializer_class = AllotmentSerializer
    search_fields = ['shop__code', 'shop__name', 'tenant__name', 'award_reference', 'source_notice']
    filterset_fields = ['shop', 'tenant', 'renewal_of']
    ordering_fields = ['start_date', 'end_date', 'shop__code', 'created_at']
    ordering = ['shop__code', '-start_date']

class RequirementViewSet(EstateViewSet):
    queryset = AllotmentRequirement.objects.select_related('allotment__shop', 'allotment__tenant', 'verified_by')
    serializer_class = RequirementSerializer
    filterset_fields = ['allotment', 'kind', 'applicable']
    search_fields = ['allotment__shop__code', 'allotment__tenant__name', 'submission_reference', 'unresolved_issue']
    ordering_fields = ['due_date', 'created_at']
    ordering = ['due_date', 'pk']


class RentRevisionSerializer(serializers.ModelSerializer):
    shop_code = serializers.CharField(source='original_award.shop.code', read_only=True)

    class Meta:
        model = RentRevision
        fields = '__all__'
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class RentRevisionViewSet(EstateViewSet):
    queryset = RentRevision.objects.select_related('original_award__shop', 'original_award__tenant')
    serializer_class = RentRevisionSerializer
    filterset_fields = ['original_award']
    search_fields = ['original_award__shop__code', 'approval_reference', 'reason']
    ordering_fields = ['effective_date', 'created_at']
    ordering = ['effective_date', 'pk']

    @action(detail=True, methods=['get'], url_path='annual-preview')
    def annual_preview(self, request, pk=None):
        through = serializers.DateField().run_validation(request.query_params.get('through', timezone.localdate().isoformat()))
        selected = self.get_object()
        latest = selected.original_award.rent_revisions.filter(effective_date__lte=through).order_by('-effective_date').first()
        if latest is None:
            raise serializers.ValidationError('The preview date precedes the recorded accepted rate.')
        from .billing import annual_revisions
        revisions = annual_revisions(latest.rate, latest.effective_date, through)
        return Response({'original_award': selected.original_award_id, 'as_of': latest.effective_date.isoformat(),
            'revisions': [{'effective_date': item['effective_date'].isoformat(), 'rate': f"{item['rate']:.4f}"}
                          for item in revisions]})


class EstateAttentionView(ListAPIView):
    """One paginated action list; contractual expiry never asserts physical vacancy."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        cutoff = today + dt.timedelta(days=90)
        rows = []
        for term in allotment_queryset():
            base = {'allotment': term.pk, 'shop': term.shop_id, 'shop_code': term.shop.code,
                'tenant': term.tenant_id, 'tenant_name': term.tenant.name,
                'end_date': term.effective_end.isoformat(), 'as_of': today.isoformat(),
                'days_remaining': (term.effective_end - today).days}
            if term.notice_governed and term.start_date <= today <= term.effective_end:
                from .billing import rent_schedule
                try:
                    schedule = rent_schedule(term, today.year, today.month)
                except ModelValidationError as exc:
                    rows.append({**base, 'kind': 'revision_due', 'due_date': term.start_date.isoformat(),
                                 'rate_issue': '; '.join(exc.messages)})
                else:
                    if schedule['missing_revision_dates']:
                        rows.append({**base, 'kind': 'revision_due',
                            'due_date': schedule['missing_revision_dates'][0].isoformat(),
                            'rate_issue': 'An April rent revision requires approval.'})
            successor = getattr(term, 'renewal', None)
            approved_successor = bool(successor and successor.approval_reference)
            if today <= term.effective_end <= cutoff:
                rows.append({**base, 'kind': 'ending', 'renewal_approved': approved_successor})
            physical_successor = bool(successor and successor.start_date <= today and
                                      successor.possession_origin is not None and
                                      successor.possession_origin.pk != successor.pk)
            continued = physical_successor
            while successor:
                if successor.approval_reference and successor.start_date <= today <= successor.effective_end:
                    continued = True
                successor = getattr(successor, 'renewal', None)
            if term.effective_end < today and not continued and not term.handover_date:
                rows.append({**base, 'kind': 'expired_unvacated' if term.possession_origin else 'handover_unknown',
                    'vacation_due_date': term.vacation_due_date.isoformat()})
                if term.vacation_due_date < today:
                    rows.append({**base, 'kind':'vacation_overdue','due_date':term.vacation_due_date.isoformat()})
            if (term.notice_governed and today <= term.effective_end <= cutoff and not approved_successor
                    and term.extension_number < 2 and not any(c.kind=='extension_fee' for c in term.charges.all())):
                rows.append({**base,'kind':'renewal_review','due_date':term.effective_end.isoformat()})
        from ..views.bills import bill_read_queryset
        for bill in bill_read_queryset():
            if bill.billing_category=='legacy':
                kind='legacy_review'
            elif bill.deadline_established and bill.due_date<today and (bill.balance_due or bill.penalty):
                kind='bill_due'
            else:
                continue
            rows.append({'kind':kind, 'bill':bill.pk,'allotment':bill.allotment_id,
                'shop':bill.allotment.shop_id if bill.allotment_id else None,
                'shop_code':bill.allotment.shop.code if bill.allotment_id else 'Unassigned',
                'tenant':bill.tenant_id,'tenant_name':bill.tenant.name,'as_of':today.isoformat(),
                'due_date':bill.due_date.isoformat() if bill.deadline_established else None})
        for requirement in RequirementViewSet.queryset.filter(applicable=True, verified_on__isnull=True):
            if (requirement.unresolved_issue or requirement.kind == 'food'
                    or (requirement.due_date and requirement.due_date < today)):
                rows.append({'kind': 'requirement', 'requirement': requirement.pk,
                    'requirement_kind': requirement.kind, 'allotment': requirement.allotment_id,
                    'shop': requirement.allotment.shop_id, 'shop_code': requirement.allotment.shop.code,
                    'tenant': requirement.allotment.tenant_id, 'tenant_name': requirement.allotment.tenant.name,
                    'due_date': requirement.due_date.isoformat() if requirement.due_date else None,
                    'as_of': today.isoformat()})
        for shop in Shop.objects.filter(active=True):
            if shop.occupancy_status == 'unknown':
                rows.append({'kind': 'availability_unknown', 'shop': shop.pk, 'shop_code': shop.code,
                             'as_of': today.isoformat()})
        from .charges import charge_queryset
        for charge in charge_queryset().filter(due_date__lt=today):
            if charge.balance_due:
                rows.append({'kind': 'charge_due', 'charge': charge.pk, 'allotment': charge.allotment_id,
                    'shop': charge.allotment.shop_id, 'shop_code': charge.allotment.shop.code,
                    'tenant': charge.allotment.tenant_id, 'tenant_name': charge.allotment.tenant.name,
                    'due_date': charge.due_date.isoformat(), 'as_of': today.isoformat()})
        from .security_api import security_summary
        for root in allotment_queryset().filter(renewal_of__isnull=True):
            account = security_summary(root)
            base = {'security':root.pk,'allotment':root.pk,'shop':root.shop_id,'shop_code':root.shop.code,
                    'tenant':root.tenant_id,'tenant_name':root.tenant.name,'as_of':today.isoformat()}
            if root.notice_governed and root.security_required_amount is None:
                rows.append({**base,'kind':'security_review','due_date':None})
            if account['deposit_overdue']:
                rows.append({**base,'kind':'deposit_due','due_date':account['effective_due_date'],
                             'shortfall':account['outstanding_requirement']})
            if root.security_held>0 and root.security_refund_review_due<today:
                rows.append({**base,'kind':'refund_review','due_date':account['refund_review_due']})
        kind = request.query_params.get('kind')
        if kind:
            rows = [row for row in rows if row['kind'] == kind]
        priority = {'expired_unvacated': 0, 'handover_unknown': 1, 'ending': 2, 'revision_due': 3, 'requirement': 4,
                    'charge_due': 5, 'deposit_due':6,'refund_review':7,'security_review':8,'availability_unknown':9,
                    'vacation_overdue':1,'bill_due':5,'renewal_review':3,'legacy_review':10}
        rows.sort(key=lambda row: (priority[row['kind']], row.get('due_date') or row.get('end_date') or '', row['shop_code']))
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(page)
