import calendar
import datetime

from django.db import transaction
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Bill, Tenant
from ..serializers import BillListSerializer, BillSerializer


def bill_read_queryset():
    return Bill.objects.select_related('tenant', 'created_by').annotate(
        _amount_paid=Coalesce(Sum('payments__amount'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
        _penalty_paid_total=Coalesce(Sum('payments__penalty_paid'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
        _penalty_paid=Coalesce(Sum(
            'payments__penalty_paid',
            filter=Q(issue_date__isnull=False, payments__payment_date__gt=F('due_date')),
        ), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)),
    ).prefetch_related('payments')


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.select_related('tenant', 'created_by')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tenant', 'month', 'year', 'status', 'tenant__type']
    search_fields = ['invoice_no', 'tenant__name']
    ordering_fields = ['year', 'month', 'due_date', 'status', 'created_at']
    ordering = ['-year', '-month']

    def get_queryset(self):
        return bill_read_queryset()

    def get_serializer_class(self):
        return BillListSerializer if self.action == 'list' else BillSerializer

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        try:
            tenant_id = int(request.data.get('tenant'))
            from_month = int(request.data.get('from_month'))
            from_year = int(request.data.get('from_year'))
            to_month = int(request.data.get('to_month'))
            to_year = int(request.data.get('to_year'))
        except (TypeError, ValueError):
            return Response({'error': 'Allottee, from month/year, and to month/year are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not (1 <= from_month <= 12 and 1 <= to_month <= 12):
            return Response({'error': 'Months must be between 1 and 12.'}, status=status.HTTP_400_BAD_REQUEST)

        start_index = from_year * 12 + from_month
        end_index = to_year * 12 + to_month
        if end_index < start_index:
            return Response({'error': 'To month must be after from month.'}, status=status.HTTP_400_BAD_REQUEST)
        if end_index - start_index + 1 > 36:
            return Response({'error': 'Bulk bill creation is limited to 36 months at a time.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = get_object_or_404(Tenant, id=tenant_id, active=True)
        try:
            due_date = datetime.date.fromisoformat(request.data.get('due_date'))
        except (TypeError, ValueError):
            if request.data.get('due_date'):
                return Response({'error': 'A valid due date is required.'}, status=status.HTTP_400_BAD_REQUEST)
            due_date = None

        month_item_map = {}
        for item in request.data.get('month_items') or []:
            try:
                item_month = int(item.get('month'))
                item_year = int(item.get('year'))
            except (TypeError, ValueError):
                return Response({'error': 'Each electricity row must include a valid month and year.'}, status=status.HTTP_400_BAD_REQUEST)
            month_item_map[(item_year, item_month)] = item

        created = []
        skipped = []
        common_fields = {
            'tenant': tenant.id,
            'rent': request.data.get('rent', 0),
            'water': request.data.get('water', 0),
            'gst_treatment': request.data.get('gst_treatment', 'cgst_sgst'),
            'notes': request.data.get('notes', ''),
        }

        with transaction.atomic():
            for index in range(start_index, end_index + 1):
                year = (index - 1) // 12
                month = (index - 1) % 12 + 1
                month_name = calendar.month_abbr[month]
                if Bill.objects.filter(tenant=tenant, month=month, year=year).exists():
                    skipped.append({'month': month, 'month_name': month_name, 'year': year, 'reason': 'Already exists'})
                    continue

                month_item = month_item_map.get((year, month), {})
                serializer = BillSerializer(
                    data={
                        **common_fields,
                        'electric': month_item.get('electric', request.data.get('electric', 0)) or 0,
                        'electric_reading': month_item.get('electric_reading', request.data.get('electric_reading', '')) or '',
                        'month': month,
                        'year': year,
                        **({'due_date': due_date.isoformat()} if due_date else {}),
                    },
                    context={'request': request}
                )
                serializer.is_valid(raise_exception=True)
                bill = serializer.save()
                created.append(BillListSerializer(bill, context={'request': request}).data)

        return Response({
            'created_count': len(created),
            'skipped_count': len(skipped),
            'created': created,
            'skipped': skipped,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
