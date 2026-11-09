from decimal import Decimal

from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Tenant, SystemSettings
from .bills import bill_read_queryset


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    # Dashboard values are intentionally computed from bill/payment state, so
    # list page totals and dashboard cards stay consistent.
    bills = bill_read_queryset()
    settings = SystemSettings.get_settings()

    total_billed = Decimal('0')
    total_collected = Decimal('0')
    total_outstanding = Decimal('0')
    total_penalty = Decimal('0')
    status_counts = {'Unpaid': 0, 'Partial': 0, 'Paid': 0}
    type_breakdown = {
        tenant_type.lower(): {'count': 0, 'billed': Decimal('0'), 'collected': Decimal('0')}
        for tenant_type in ['Shop', 'Canteen', 'Contractor']
    }

    for bill in bills:
        bill._penalty_config = bill.tenant.get_penalty_config(settings)
        bill_total = bill.total_amount
        paid = bill.amount_paid
        tenant_key = bill.tenant.type.lower()

        total_billed += bill_total
        total_collected += paid
        if bill.status in status_counts:
            status_counts[bill.status] += 1
        if bill.status in ['Unpaid', 'Partial']:
            total_outstanding += bill.balance_due
            total_penalty += bill.penalty
        if tenant_key in type_breakdown:
            type_breakdown[tenant_key]['billed'] += bill_total
            type_breakdown[tenant_key]['collected'] += paid

    tenant_counts = dict(
        Tenant.objects.filter(active=True)
        .values_list('type')
        .annotate(count=Count('id'))
    )
    for tenant_type in ['Shop', 'Canteen', 'Contractor']:
        type_breakdown[tenant_type.lower()]['count'] = tenant_counts.get(tenant_type, 0)

    data = {
        'total_tenants': Tenant.objects.count(),
        'active_tenants': Tenant.objects.filter(active=True).count(),
        'total_billed': float(total_billed),
        'total_collected': float(total_collected),
        'total_outstanding': float(total_outstanding),
        'total_penalty': float(total_penalty),
        'unpaid_count': status_counts['Unpaid'],
        'partial_count': status_counts['Partial'],
        'paid_count': status_counts['Paid'],
        'type_breakdown': type_breakdown,
    }

    return Response(data)
