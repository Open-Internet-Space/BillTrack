import calendar
import datetime
from decimal import Decimal
from django.utils import timezone

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Bill, SystemSettings
from ..activity.api import AuditedViewSetMixin
from ..serializers import BillListSerializer, BillRangeSerializer, BillSerializer
from ..estate.billing import annual_revisions, holiday_rent
from ..estate.legacy import legacy_preview, legacy_confirm


def preview_month(bill, settings, existing=False, recalculate_tax=True):
    waiver = holiday_rent(bill.full_month_rent if bill.full_month_rent is not None else bill.rent,
                          bill.year, bill.month, bill.holiday_start_date, bill.holiday_end_date)
    if recalculate_tax:
        bill.gst_on_rent, bill.cgst_on_rent, bill.sgst_on_rent, bill.igst_on_rent = bill.calculate_gst(settings)
    due_date = bill.due_date
    warnings = []
    if bill.billing_policy == 'notices_368_369':
        due_date = bill.raised_date + datetime.timedelta(days=7) if bill.raised_date else None
        if bill.rent_revision_id:
            through = datetime.date(bill.year, bill.month, calendar.monthrange(bill.year, bill.month)[1])
            warnings = [f"April revision needs approval: {item['effective_date'].isoformat()}"
                        for item in annual_revisions(bill.rate_snapshot, bill.rent_revision.effective_date, through, flat=bill.area_snapshot is None)]
        else:
            warnings = ['Accepted rate schedule is not recorded.']
    bill.due_date = due_date
    bill._penalty_config = bill.tenant.get_penalty_config(settings)
    payments = list(bill.payments.all()) if bill.pk else []
    paid = sum((payment.amount for payment in payments), Decimal('0'))
    interest_paid = sum((payment.penalty_paid for payment in payments), Decimal('0'))
    interest = bill.accrued_penalty(timezone.localdate()) if bill.pk else Decimal('0')
    return {
        'principal_paid': f'{paid:.2f}', 'interest_paid': f'{interest_paid:.2f}',
        'interest_accrued': f'{interest:.2f}',
        'excess_principal_paid': f"{max(Decimal('0'), paid - bill.total_amount):.2f}",
        'excess_interest_paid': f"{max(Decimal('0'), interest_paid - interest):.2f}",
        'billing_policy': bill.billing_policy, 'raised_date': bill.raised_date.isoformat() if bill.raised_date else None,
        'due_date': due_date.isoformat() if due_date else None, 'receipt_status': bill.receipt_status,
        'rent_revision': bill.rent_revision_id, 'rent_revision_reference': bill.rent_revision_reference,
        'rate_snapshot': f'{bill.rate_snapshot:.4f}' if bill.rate_snapshot is not None else None,
        'area_snapshot': f'{bill.area_snapshot:.4f}' if bill.area_snapshot is not None else None,
        'rate_warnings': warnings,
        'year': bill.year, 'month': bill.month, 'month_name': calendar.month_abbr[bill.month],
        'days_in_month': waiver['days_in_month'], 'holiday_closed_days': waiver['closed_days'],
        'holiday_waiver': f"{waiver['waiver_amount']:.2f}",
        **{key: f'{getattr(bill, key):.2f}' if getattr(bill, key) is not None else None
           for key in ('full_month_rent', 'rent', 'electric', 'water', 'gst_on_rent',
                       'cgst_on_rent', 'sgst_on_rent', 'igst_on_rent', 'total_amount')},
        'already_exists': existing,
    }


def bill_read_queryset():
    return Bill.objects.select_related('tenant', 'created_by', 'allotment__shop').annotate(
        _amount_paid=Coalesce(Sum('payments__amount'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
        _penalty_paid_total=Coalesce(Sum('payments__penalty_paid'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
        _penalty_paid=Coalesce(Sum(
            'payments__penalty_paid',
            filter=Q(issue_date__isnull=False, payments__payment_date__gt=F('due_date')),
        ), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
    ).prefetch_related('payments')


class BillViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    queryset = Bill.objects.select_related('tenant', 'created_by')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tenant', 'allotment', 'billing_category', 'month', 'year', 'status', 'tenant__type']
    search_fields = ['invoice_no', 'tenant__name', 'tenant__allotment_description', 'allotment__shop__code']
    ordering_fields = ['year', 'month', 'due_date', 'status', 'created_at']
    ordering = ['-year', '-month']

    def get_queryset(self):
        return bill_read_queryset()

    def get_serializer_class(self):
        return BillListSerializer if self.action == 'list' else BillSerializer

    @action(detail=True, methods=['post'], url_path='legacy-preview')
    def review_legacy(self, request, pk=None):
        return Response(legacy_preview(self.get_object(), request.data, request.user))

    @action(detail=True, methods=['post'], url_path='legacy-confirm')
    def confirm_legacy(self, request, pk=None):
        return Response(legacy_confirm(pk, request.data.get('confirmation', ''), request.user, 'api'))

    @action(detail=False, methods=['post'])
    def preview(self, request):
        serializer = BillRangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        settings = SystemSettings.objects.first() or SystemSettings()
        months = []
        for row in serializer.validated_data['bills']:
            bill = Bill(**row.validated_data)
            existing = Bill.objects.filter(tenant=bill.tenant, allotment=bill.allotment,
                                           year=bill.year, month=bill.month).exists()
            months.append(preview_month(bill, settings, existing))
        return Response({'months': months})

    @action(detail=True, methods=['post'], url_path='preview')
    def preview_bill(self, request, pk=None):
        bill = self.get_object()
        settings = SystemSettings.objects.first() or SystemSettings()
        bill._penalty_config = bill.tenant.get_penalty_config(settings)
        previous_interest = bill.accrued_penalty(timezone.localdate())
        serializer = BillSerializer(bill, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        changed = any(key in serializer.validated_data and serializer.validated_data[key] != getattr(bill, key)
                      for key in ('rent', 'full_month_rent', 'holiday_start_date', 'holiday_end_date',
                                  'electric', 'water', 'gst_treatment', 'year', 'month'))
        for key, value in serializer.validated_data.items():
            setattr(bill, key, value)
        result = preview_month(bill, settings, recalculate_tax=changed)
        result['previous_interest_accrued'] = f'{previous_interest:.2f}'
        return Response({'months': [result]})

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        serializer = BillRangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        created, skipped = serializer.save()
        return Response({
            'created_count': len(created), 'skipped_count': len(skipped),
            'created': BillListSerializer(created, many=True, context={'request': request}).data,
            'skipped': skipped,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
