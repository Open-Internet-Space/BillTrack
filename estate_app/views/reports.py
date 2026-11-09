"""Read-only reports; exports use a signed copy of the reviewed preview."""
import csv
import datetime as dt
import io
from decimal import Decimal

from django.core import signing
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from weasyprint import HTML

from ..models import Bill, Payment, SystemSettings, Tenant
from .report_exports import document_bytes, workbook_bytes


TITLES = {'payments': 'Payments received', 'pending': 'Pending bills',
          'penalties': 'Penalties', 'bills': 'Bills register', 'statement': 'Bills and payments statement'}
LABELS = {
    'vendor': 'Vendor', 'dispatch_ref_no': 'Reference / dispatch no.', 'bill_date': 'Bill date', 'period': 'Billing month',
    'receipt_status': 'Receipt status', 'due_date': 'Due date', 'status': 'Payment status',
    'payment_date': 'Payment date', 'receipt': 'Receipt number', 'days_overdue': 'Overdue days',
    'rent': 'Rent', 'gst': 'GST', 'electric': 'Electricity', 'water': 'Water',
    'billed': 'Billed', 'paid': 'Principal paid', 'balance': 'Principal due',
    'penalty_accrued': 'Penalty accrued', 'penalty_paid': 'Penalty paid',
    'penalty_due': 'Penalty due', 'total_due': 'Total due', 'received': 'Total received',
    'opening': 'Opening net dues', 'penalty_movement': 'Penalty accrued in period', 'closing': 'Closing net dues',
}
MONEY_FIELDS = set('rent gst electric water billed paid balance penalty_accrued penalty_paid penalty_due total_due received opening penalty_movement closing'.split())
SCHEMAS = {
    'payments': 'payment_date vendor receipt dispatch_ref_no bill_date period paid penalty_paid received',
    'pending': 'vendor dispatch_ref_no bill_date period receipt_status due_date status billed paid balance penalty_due total_due',
    'penalties': 'vendor dispatch_ref_no bill_date period due_date days_overdue penalty_accrued penalty_paid penalty_due',
    'bills': 'vendor dispatch_ref_no bill_date period receipt_status status rent gst electric water billed paid balance',
    'statement': 'vendor opening billed penalty_movement paid penalty_paid received closing',
}
HISTORY_NOTE = ('Historical reports reconstruct payment timing using current bill, vendor and penalty settings. '
                'Edits, deletions and earlier settings are not retained as a historical audit trail.')
ZERO = Decimal('0')


class ReportFilters(serializers.Serializer):
    report = serializers.ChoiceField(choices=list(TITLES), default='pending')
    start = serializers.DateField(required=False)
    to = serializers.DateField(default=timezone.localdate)
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all(), required=False)
    type = serializers.ChoiceField(choices=['', 'Shop', 'Canteen', 'Contractor'], default='')
    status = serializers.ChoiceField(choices=['', 'Unpaid', 'Partial', 'Paid'], default='')
    receipt_status = serializers.ChoiceField(choices=['', 'pending', 'confirmed'], default='')
    billing_from = serializers.RegexField(r'^\d{4}-(0[1-9]|1[0-2])$', required=False)
    billing_to = serializers.RegexField(r'^\d{4}-(0[1-9]|1[0-2])$', required=False)
    output = serializers.ChoiceField(choices=['json', 'csv', 'pdf', 'xlsx', 'docx'], default='json')

    def validate(self, attrs):
        end = attrs['to']
        if end > timezone.localdate() or end.year < 2000:
            raise serializers.ValidationError('Cutoff must be between 1 January 2000 and today.')
        if attrs.get('start', end) > end or attrs.get('start', end).year < 2000:
            raise serializers.ValidationError('From date must be between 1 January 2000 and the cutoff.')
        for key in ('billing_from', 'billing_to'):
            if key in attrs and not '2000-01' <= attrs[key] <= '2100-12':
                raise serializers.ValidationError('Billing months must be between 2000 and 2100.')
        if attrs.get('billing_from', '') > attrs.get('billing_to', '9999-12'):
            raise serializers.ValidationError('Billing month range is reversed.')
        return attrs


def bill_position(bill, cutoff):
    """Reconstruct a bill position without using its stored, present-day status."""
    payments = [payment for payment in bill.payments.all() if payment.payment_date <= cutoff]
    paid = sum((payment.amount for payment in payments), ZERO)
    penalty_paid = sum((payment.penalty_paid for payment in payments), ZERO)
    billed = bill.total_amount if (bill.year, bill.month) <= (cutoff.year, cutoff.month) else ZERO
    confirmed = bool(bill.issue_date and bill.issue_date <= cutoff)
    accrued = bill.accrued_penalty(cutoff) if billed and confirmed else ZERO
    eligible_penalty_paid = sum((payment.penalty_paid for payment in payments
                                if bill.penalty_start_date and payment.payment_date > bill.penalty_start_date), ZERO)
    balance = max(ZERO, billed - paid)
    penalty_due = max(ZERO, accrued - eligible_penalty_paid)
    penalty_end, running_paid = cutoff, ZERO
    for payment in payments:
        running_paid += payment.amount
        if running_paid >= bill.total_amount:
            penalty_end = payment.payment_date
            break
    days = max(0, (penalty_end - bill.due_date).days) if billed and confirmed else 0
    return {'billed': billed, 'paid': paid, 'penalty_paid': penalty_paid,
            'penalty_accrued': accrued, 'penalty_due': penalty_due, 'balance': balance,
            'days_overdue': days, 'total_due': balance + penalty_due, 'net': billed + accrued - paid - penalty_paid}


def build_report(filters):
    kind, end = filters['report'], filters['to']
    start = filters.get('start')
    if kind == 'statement' and not start:
        start = end.replace(day=1)
    settings = SystemSettings.get_settings()
    bills = Bill.objects.select_related('tenant').filter(
        Q(year__lt=end.year) | Q(year=end.year, month__lte=end.month) | Q(payments__payment_date__lte=end)
    ).distinct().prefetch_related(Prefetch('payments', queryset=Payment.objects.filter(payment_date__lte=end).order_by('payment_date', 'pk')))
    if filters.get('tenant'):
        bills = bills.filter(tenant=filters['tenant'])
    if filters['type']:
        bills = bills.filter(tenant__type=filters['type'])
    if 'billing_from' in filters:
        year, month = map(int, filters['billing_from'].split('-'))
        bills = bills.filter(Q(year__gt=year) | Q(year=year, month__gte=month))
    if 'billing_to' in filters:
        year, month = map(int, filters['billing_to'].split('-'))
        bills = bills.filter(Q(year__lt=year) | Q(year=year, month__lte=month))
    rows, statements = [], {}
    for bill in bills.order_by('tenant__name', 'tenant_id', 'year', 'month', 'pk'):
        bill._penalty_config = bill.tenant.get_penalty_config(settings)
        position = bill_position(bill, end)
        confirmed = bool(bill.issue_date and bill.issue_date <= end)
        status = 'Paid' if position['total_due'] == 0 else ('Partial' if position['paid'] > 0 else 'Unpaid')
        if filters['status'] and filters['status'] != status:
            continue
        if filters['receipt_status'] and confirmed != (filters['receipt_status'] == 'confirmed'):
            continue
        common = {'vendor': bill.tenant.name, 'dispatch_ref_no': bill.dispatch_ref_no,
                  'bill_date': bill.issue_date.isoformat() if confirmed else '',
                  'period': f'{bill.year:04d}-{bill.month:02d}',
                  'receipt_status': 'Receipt Confirmed' if confirmed else 'Pending Receipt',
                  'due_date': bill.due_date.isoformat() if confirmed else '', 'status': status}
        if kind == 'payments':
            for payment in bill.payments.all():
                if not start or payment.payment_date >= start:
                    rows.append({**common, 'payment_date': payment.payment_date.isoformat(), 'receipt': payment.receipt_no,
                                 'paid': payment.amount, 'penalty_paid': payment.penalty_paid,
                                 'received': payment.amount + payment.penalty_paid})
        elif kind == 'statement':
            opening = bill_position(bill, start - dt.timedelta(days=1))
            row = statements.setdefault(bill.tenant_id, {'vendor': bill.tenant.name, **dict.fromkeys(
                SCHEMAS['statement'].split()[1:], ZERO)})
            row['opening'] += opening['net']
            row['billed'] += position['billed'] - opening['billed']
            row['penalty_movement'] += position['penalty_accrued'] - opening['penalty_accrued']
            row['paid'] += position['paid'] - opening['paid']
            row['penalty_paid'] += position['penalty_paid'] - opening['penalty_paid']
            row['received'] = row['paid'] + row['penalty_paid']
            row['closing'] += position['net']
        else:
            if kind == 'bills':
                if (bill.year, bill.month) > (end.year, end.month):
                    continue
                if start and (bill.year, bill.month) < (start.year, start.month):
                    continue
            if kind == 'pending' and position['total_due'] <= 0:
                continue
            if kind == 'penalties' and position['penalty_accrued'] == 0 and position['penalty_paid'] == 0:
                continue
            rows.append({**common, **{key: value for key, value in position.items() if key != 'net'},
                         'rent': bill.rent, 'gst': bill.gst_on_rent, 'electric': bill.electric, 'water': bill.water})
    if kind == 'statement':
        rows = list(statements.values())
    if kind == 'payments':
        rows.sort(key=lambda row: (row['payment_date'], row['vendor'], row['dispatch_ref_no'], row['receipt']))
    columns = [{'key': key, 'label': LABELS[key], 'numeric': key in MONEY_FIELDS} for key in SCHEMAS[kind].split()]
    total_keys = MONEY_FIELDS.intersection(SCHEMAS[kind].split())
    totals = {key: f'{sum((row.get(key, ZERO) for row in rows), ZERO):.2f}' for key in sorted(total_keys)}
    for row in rows:
        for key, value in row.items():
            if isinstance(value, Decimal):
                row[key] = f'{value:.2f}'
    descriptions = [f'Cutoff: {end.isoformat()}']
    if kind in ('payments', 'bills', 'statement'):
        descriptions.append(f'{"Billing months" if kind == "bills" else "Period"}: {start.isoformat() if start else "All history"} to {end.isoformat()}')
    for key, label in [('tenant', 'Vendor'), ('type', 'Vendor type'), ('status', 'Status'),
                       ('receipt_status', 'Receipt'), ('billing_from', 'Billing from'), ('billing_to', 'Billing to')]:
        if filters.get(key):
            value = filters[key].name if key == 'tenant' else filters[key]
            descriptions.append(f'{label}: {value}')
    notes = [HISTORY_NOTE, 'All amounts in INR. Bills are assigned to their accounting month; receipts use payment date.']
    if kind == 'pending':
        notes.append('Includes all matching bills through the cutoff, including earlier unpaid periods.')
    if kind == 'penalties':
        notes.append('Includes accrued and collected penalties, including settled bills. Penalty dues credit payments after the confirmed deadline, as in bill calculations.')
    if kind == 'statement':
        notes.append('Opening net dues + billed + penalty accrued in period − total received = closing net dues. Negative dues represent credits.')
    return {'title': TITLES[kind], 'kind': kind, 'organisation': settings.letterhead_name,
            'department': settings.letterhead_department, 'filters': ' · '.join(descriptions),
            'generated_at': timezone.localtime().strftime('%Y-%m-%d %H:%M:%S %Z'),
            'columns': columns, 'rows': rows, 'count': len(rows), 'totals': totals, 'notes': notes}


def export_report(data, output):
    if output == 'pdf':
        content = HTML(string=render_to_string('report.html', {'report': data})).write_pdf()
        mime = 'application/pdf'
    elif output == 'docx':
        content = document_bytes(data)
        mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif output == 'xlsx':
        content = workbook_bytes(data)
        mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow([data['title'], data['filters'], data['generated_at']])
        writer.writerow([column['label'] for column in data['columns']])
        def safe(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
        for row in data['rows']:
            writer.writerow([safe(row.get(column['key'], '')) for column in data['columns']])
        writer.writerow([safe(data['totals'].get(column['key'], 'Totals' if index == 0 else ''))
                         for index, column in enumerate(data['columns'])])
        for note in data['notes']:
            writer.writerow([note])
        content, mime = stream.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8'
    response = HttpResponse(content, content_type=mime)
    response['Content-Disposition'] = f'attachment; filename="{data["kind"]}-report.{output}"'
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reports(request):
    if request.method == 'POST':
        output = request.data.get('output')
        if output not in ('docx', 'xlsx', 'pdf', 'csv'):
            raise serializers.ValidationError('Choose DOCX, XLSX or PDF.')
        try:
            snapshot = request.data.get('snapshot', '')
            if not isinstance(snapshot, str):
                raise signing.BadSignature('Invalid snapshot')
            payload = signing.loads(snapshot, salt='reports', max_age=3600)
            if payload['user'] != request.user.pk:
                raise signing.BadSignature('Wrong user')
        except (signing.BadSignature, TypeError, ValueError, KeyError):
            raise serializers.ValidationError('Preview expired or invalid. Generate a new preview before downloading.')
        data = payload['data']
        available = [column['key'] for column in data['columns']]
        selected = serializers.ListField(child=serializers.ChoiceField(choices=available), allow_empty=False).run_validation(
            request.data.get('columns', available))
        data = {**data, 'columns': [column for column in data['columns'] if column['key'] in selected]}
        return export_report(data, output)
    params = request.query_params.dict()
    if 'from' in params:
        params['start'] = params.pop('from')
    serializer = ReportFilters(data=params)
    serializer.is_valid(raise_exception=True)
    data = build_report(serializer.validated_data)
    output = serializer.validated_data['output']
    if output != 'json':
        return export_report(data, output)
    snapshot = signing.dumps({'user': request.user.pk, 'data': data}, salt='reports', compress=True)
    response = Response({**data, 'snapshot': snapshot})
    response['Cache-Control'] = 'no-store'
    return response
