from decimal import Decimal
from functools import wraps

from django.db.models import Count
from django.db import OperationalError
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Tenant, SystemSettings, SecurityMovement
from .bills import bill_read_queryset
from ..estate.charges import charge_queryset


def locked_read(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except OperationalError as error:
            if 'locked' not in str(error).lower():
                raise
            return Response({'detail': 'Another change is in progress. Retry to load current records.'}, status=409)
    return wrapper


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@locked_read
def dashboard_stats(request):
    # Dashboard values are intentionally computed from bill/payment state, so
    # list page totals and dashboard cards stay consistent.
    bills = bill_read_queryset()
    settings = SystemSettings.get_settings()

    total_billed = Decimal('0')
    total_collected = Decimal('0')
    total_settled = Decimal('0')
    total_outstanding = Decimal('0')
    total_penalty = Decimal('0')
    status_counts = {'Unpaid': 0, 'Partial': 0, 'Paid': 0}
    type_breakdown = {
        tenant_type.lower(): {'count': 0, 'billed': Decimal('0'), 'collected': Decimal('0')}
        for tenant_type in ['Shop', 'Canteen', 'Contractor']
    }

    for bill in bills:
        if bill.is_draft:
            continue
        bill._penalty_config = bill.tenant.get_penalty_config(settings)
        bill_total = bill.total_amount
        paid = bill.amount_paid
        cash_paid = sum((row.amount for row in bill.payments.all() if row.source=='receipt'),Decimal('0'))
        tenant_key = bill.tenant.type.lower()

        total_billed += bill_total
        total_collected += cash_paid
        total_settled += paid
        if bill.status in status_counts:
            status_counts[bill.status] += 1
        if bill.status in ['Unpaid', 'Partial']:
            total_outstanding += bill.balance_due
            total_penalty += bill.penalty
        if tenant_key in type_breakdown:
            type_breakdown[tenant_key]['billed'] += bill_total
            type_breakdown[tenant_key]['collected'] += cash_paid

    charge_totals = {key: Decimal('0') for key in ['assessed', 'paid', 'applied', 'waived', 'outstanding']}
    charge_counts = {'open_count': 0, 'overdue_count': 0}
    for charge in charge_queryset():
        charge_totals['assessed'] += charge.gross_amount
        cash_paid = sum((row.amount for row in charge.payments.all() if row.source=='receipt'),Decimal('0'))
        charge_totals['paid'] += cash_paid
        charge_totals['applied'] += charge.amount_paid-cash_paid
        total_settled += charge.amount_paid
        charge_totals['waived'] += charge.waiver_amount
        charge_totals['outstanding'] += charge.balance_due
        charge_counts['open_count'] += bool(charge.balance_due)
        charge_counts['overdue_count'] += bool(charge.overdue)
        tenant_key = charge.allotment.tenant.type.lower()
        if tenant_key in type_breakdown:
            type_breakdown[tenant_key]['billed'] += charge.gross_amount
            type_breakdown[tenant_key]['collected'] += cash_paid
    total_billed += charge_totals['assessed']
    total_collected += charge_totals['paid']
    total_outstanding += charge_totals['outstanding']
    security_totals = {kind:Decimal('0') for kind in ['received','refunded','applied','forfeited']}
    for movement in SecurityMovement.objects.all():
        security_totals[movement.kind] += movement.amount
    security_totals['held'] = security_totals['received']-sum(
        (security_totals[kind] for kind in ['refunded','applied','forfeited']),Decimal('0'))

    tenant_counts = dict(
        Tenant.objects.filter(active=True)
        .values_list('type')
        .annotate(count=Count('id'))
    )
    for tenant_type in ['Shop', 'Canteen', 'Contractor']:
        type_breakdown[tenant_type.lower()]['count'] = tenant_counts.get(tenant_type, 0)

    data = {
        'as_of': timezone.localdate().isoformat(),
        'total_tenants': Tenant.objects.count(),
        'active_tenants': Tenant.objects.filter(active=True).count(),
        'total_billed': float(total_billed),
        'total_collected': float(total_collected),
        'total_settled': float(total_settled),
        'total_outstanding': float(total_outstanding),
        'total_penalty': float(total_penalty),
        'unpaid_count': status_counts['Unpaid'],
        'partial_count': status_counts['Partial'],
        'paid_count': status_counts['Paid'],
        'type_breakdown': type_breakdown,
        'charge_summary': {**{key: f'{value:.2f}' for key, value in charge_totals.items()}, **charge_counts},
        'security_summary': {key:f'{value:.2f}' for key,value in security_totals.items()},
    }

    return Response(data)
