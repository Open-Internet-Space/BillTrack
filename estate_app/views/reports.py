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

from ..models import Allotment, Bill, EstateCharge, Payment, SecurityMovement, SystemSettings, Tenant
from .report_exports import document_bytes, workbook_bytes


TITLES = {'payments': 'Payments received', 'pending': 'Pending bills',
          'penalties': 'Penalties', 'bills': 'Bills register', 'statement': 'Bills and payments statement',
          'estate': 'Estate dues and security statement'}
LABELS = {
    'vendor': 'Vendor', 'dispatch_ref_no': 'Reference / dispatch no.', 'bill_date': 'Bill date', 'period': 'Billing month',
    'receipt_status': 'Receipt status', 'due_date': 'Due date', 'status': 'Payment status',
    'payment_date': 'Payment date', 'receipt': 'Receipt number', 'days_overdue': 'Overdue days',
    'rent': 'Rent', 'gst': 'GST', 'electric': 'Electricity', 'water': 'Water',
    'billed': 'Billed', 'paid': 'Principal paid', 'balance': 'Principal due',
    'penalty_accrued': 'Penalty accrued', 'penalty_paid': 'Penalty paid',
    'penalty_due': 'Penalty due', 'total_due': 'Total due', 'received': 'Cash received',
    'opening': 'Opening net dues', 'penalty_movement': 'Penalty accrued in period', 'closing': 'Closing net dues',
    'security_applied': 'Security applied (noncash)',
    'award':'Allotment', 'policy':'Billing policy', 'entry':'Entry / reference',
    'holiday_waiver':'Holiday rent waived', 'charge_due':'One-off charge due',
    'charge_waived':'Charge waived', 'security_held':'Security liability movement',
}
MONEY_FIELDS = set('rent gst electric water billed paid balance penalty_accrued penalty_paid penalty_due total_due received opening penalty_movement closing security_applied'.split())
SCHEMAS = {
    'payments': 'payment_date vendor award policy receipt dispatch_ref_no bill_date period paid penalty_paid received',
    'pending': 'vendor award policy dispatch_ref_no bill_date period receipt_status due_date status billed paid balance penalty_due total_due',
    'penalties': 'vendor award policy dispatch_ref_no bill_date period due_date days_overdue penalty_accrued penalty_paid penalty_due',
    'bills': 'vendor award policy dispatch_ref_no bill_date period receipt_status status rent gst electric water billed paid balance',
    'statement': 'vendor award opening billed penalty_movement paid penalty_paid received security_applied closing',
    'estate': 'vendor award entry holiday_waiver balance penalty_due charge_due charge_waived received security_applied total_due security_held',
}
MONEY_FIELDS.update(('holiday_waiver','charge_due','charge_waived','security_held'))
HISTORY_NOTE = ('Historical reports reconstruct payment timing using current bill, vendor and penalty settings. '
                'Edits, deletions and earlier settings are not retained as a historical audit trail.')
ZERO = Decimal('0')


class ReportFilters(serializers.Serializer):
    report = serializers.ChoiceField(choices=list(TITLES), default='pending')
    start = serializers.DateField(required=False)
    to = serializers.DateField(default=timezone.localdate)
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all(), required=False)
    allotment = serializers.PrimaryKeyRelatedField(queryset=Allotment.objects.all(), required=False)
    policy = serializers.ChoiceField(choices=['legacy_receipt','notices_368_369'], required=False)
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
        if attrs['report']=='estate' and any(attrs.get(key) for key in ('start','status','receipt_status','billing_from','billing_to','policy')):
            raise serializers.ValidationError('The estate statement uses the cutoff, allottee, vendor type and allotment filters.')
        return attrs


def bill_position(bill, cutoff):
    """Reconstruct a bill position without using its stored, present-day status."""
    payments = [payment for payment in bill.payments.all() if payment.payment_date <= cutoff]
    paid = sum((payment.amount for payment in payments), ZERO)
    penalty_paid = sum((payment.penalty_paid for payment in payments), ZERO)
    cash_received = sum((payment.amount+payment.penalty_paid for payment in payments if payment.source=='receipt'),ZERO)
    security_applied = sum((payment.amount+payment.penalty_paid for payment in payments if payment.source=='security_application'),ZERO)
    billed = bill.total_amount if (bill.year, bill.month) <= (cutoff.year, cutoff.month) else ZERO
    if bill.billing_policy == 'notices_368_369' and (not bill.raised_date or bill.raised_date > cutoff):
        billed = ZERO
    confirmed = bool(bill.confirmation_date and bill.confirmation_date <= cutoff)
    accrued = bill.accrued_penalty(cutoff) if billed and confirmed else ZERO
    eligible_penalty_paid = sum((payment.penalty_paid for payment in payments
                                if bill.penalty_start_date and (bill.billing_policy == 'notices_368_369'
                                    or payment.payment_date > bill.penalty_start_date)), ZERO)
    balance = max(ZERO, billed - paid)
    penalty_due = max(ZERO, accrued - eligible_penalty_paid)
    penalty_end, running_paid = cutoff, ZERO
    for payment in payments:
        running_paid += payment.amount
        if running_paid >= bill.total_amount:
            penalty_end = payment.payment_date
            break
    days = max(0, (penalty_end - bill.penalty_start_date).days) if billed and confirmed and bill.penalty_start_date else 0
    return {'billed': billed, 'paid': paid, 'penalty_paid': penalty_paid,
            'cash_received':cash_received,'security_applied':security_applied,
            'penalty_accrued': accrued, 'penalty_due': penalty_due, 'balance': balance,
            'days_overdue': days, 'total_due': balance + penalty_due, 'net': billed + accrued - paid - penalty_paid}


def estate_position_rows(filters, bills, settings):
    end = filters['to']
    terms = Allotment.objects.all()
    if filters.get('allotment'):
        terms = terms.filter(pk=filters['allotment'].pk)
    for key, field in [('tenant','tenant'),('type','tenant__type')]:
        if filters.get(key):
            terms = terms.filter(**{field:filters[key]})
    rows = []
    def add(person, term, entry, **amounts):
        rows.append({'vendor':person.display_name,
                     'award':term.award_reference if term else 'Unassigned', 'entry':entry, **amounts})
    for bill in bills.order_by('tenant__name','year','month','pk'):
        if bill.is_draft or (bill.raised_date and bill.raised_date>end):
            continue
        bill._penalty_config = bill.tenant.get_penalty_config(settings)
        position = bill_position(bill,end)
        add(bill.tenant,bill.allotment,f'{bill.invoice_no} · {bill.get_billing_policy_display()}',
            holiday_waiver=bill.holiday_waiver if (bill.year,bill.month)<=(end.year,end.month) else ZERO,
            balance=position['balance'], penalty_due=position['penalty_due'], total_due=position['total_due'],
            received=position['cash_received'],security_applied=position['security_applied'])
    for charge in EstateCharge.objects.filter(allotment__in=terms, assessed_on__lte=end).select_related(
            'allotment__tenant').prefetch_related('payments').order_by('assessed_on','pk'):
        receipts = [p for p in charge.payments.all() if p.payment_date<=end]
        paid = sum((p.amount for p in receipts if p.source=='receipt'), ZERO)
        applied = sum((p.amount for p in receipts if p.source=='security_application'), ZERO)
        waiver = charge.waiver_amount if charge.waived_at and timezone.localdate(charge.waived_at)<=end else ZERO
        due = max(ZERO,charge.gross_amount-waiver-paid-applied)
        add(charge.allotment.tenant,charge.allotment,f'{charge.get_kind_display()} · {charge.authority_reference}',
            received=paid,security_applied=applied,charge_waived=waiver,charge_due=due,total_due=due)
    roots = terms
    if filters.get('allotment'):
        roots = Allotment.objects.filter(pk=filters['allotment'].original_award.pk) if terms.exists() else terms
    for movement in SecurityMovement.objects.filter(original_award__in=roots,effective_date__lte=end).select_related(
            'original_award__tenant').order_by('effective_date','pk'):
        add(movement.original_award.tenant,movement.original_award,
            f'{movement.effective_date} · Security {movement.get_kind_display()} · {movement.reference}',
            security_held=movement.amount if movement.kind=='received' else -movement.amount)
    return rows


def build_report(filters):
    kind, end = filters['report'], filters['to']
    start = filters.get('start')
    if kind == 'statement' and not start:
        start = end.replace(day=1)
    settings = SystemSettings.get_settings()
    bills = Bill.objects.select_related('tenant','allotment').filter(
        Q(year__lt=end.year) | Q(year=end.year, month__lte=end.month) | Q(payments__payment_date__lte=end)
    ).distinct().prefetch_related(Prefetch('payments', queryset=Payment.objects.filter(payment_date__lte=end).order_by('payment_date', 'pk')))
    if filters.get('tenant'):
        bills = bills.filter(tenant=filters['tenant'])
    if filters['type']:
        bills = bills.filter(tenant__type=filters['type'])
    for key,field in [('allotment','allotment'),('policy','billing_policy')]:
        if filters.get(key):
            bills = bills.filter(**{field:filters[key]})
    if 'billing_from' in filters:
        year, month = map(int, filters['billing_from'].split('-'))
        bills = bills.filter(Q(year__gt=year) | Q(year=year, month__gte=month))
    if 'billing_to' in filters:
        year, month = map(int, filters['billing_to'].split('-'))
        bills = bills.filter(Q(year__lt=year) | Q(year=year, month__lte=month))
    rows, statements = [], {}
    if kind=='estate':
        rows = estate_position_rows(filters,bills,settings)
    for bill in bills.order_by('tenant__name', 'tenant_id', 'year', 'month', 'pk') if kind!='estate' else ():
        bill._penalty_config = bill.tenant.get_penalty_config(settings)
        position = bill_position(bill, end)
        confirmed = bool(bill.confirmation_date and bill.confirmation_date <= end)
        status = 'Paid' if position['total_due'] == 0 else ('Partial' if position['paid'] > 0 else 'Unpaid')
        if filters['status'] and filters['status'] != status:
            continue
        if filters['receipt_status'] and confirmed != (filters['receipt_status'] == 'confirmed'):
            continue
        identity = {'vendor': bill.tenant.display_name,
                    'award': bill.allotment.award_reference if bill.allotment_id else 'Unassigned'}
        common = {**identity, 'policy': bill.get_billing_policy_display(), 'dispatch_ref_no': bill.dispatch_ref_no,
                  'bill_date': (bill.raised_date.isoformat() if bill.raised_date and bill.raised_date <= end else '')
                    if bill.billing_policy == 'notices_368_369' else bill.issue_date.isoformat() if confirmed else '',
                  'period': f'{bill.year:04d}-{bill.month:02d}',
                  'receipt_status': ('Draft' if not bill.raised_date or bill.raised_date > end else
                    'Email Dispatch Confirmed' if confirmed else 'Pending Email Dispatch')
                    if bill.billing_policy == 'notices_368_369' else 'Receipt Confirmed' if confirmed else 'Pending Receipt',
                  'due_date': bill.due_date.isoformat() if bill.due_date and (confirmed or
                    (bill.billing_policy == 'notices_368_369' and bill.raised_date and bill.raised_date <= end)) else '', 'status': status}
        if kind == 'payments':
            for payment in bill.payments.all():
                if payment.source=='receipt' and (not start or payment.payment_date >= start):
                    rows.append({**common, 'payment_date': payment.payment_date.isoformat(), 'receipt': payment.receipt_no,
                                 'paid': payment.amount, 'penalty_paid': payment.penalty_paid,
                                 'received': payment.amount + payment.penalty_paid})
        elif kind == 'statement':
            opening = bill_position(bill, start - dt.timedelta(days=1))
            row = statements.setdefault((bill.tenant_id, bill.allotment_id),
                {**identity, **dict.fromkeys(SCHEMAS['statement'].split()[2:], ZERO)})
            row['opening'] += opening['net']
            row['billed'] += position['billed'] - opening['billed']
            row['penalty_movement'] += position['penalty_accrued'] - opening['penalty_accrued']
            row['paid'] += position['paid'] - opening['paid']
            row['penalty_paid'] += position['penalty_paid'] - opening['penalty_paid']
            row['received'] += position['cash_received']-opening['cash_received']
            row['security_applied'] += position['security_applied']-opening['security_applied']
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
    for key, label in [('tenant', 'Vendor'), ('allotment','Award'),('policy','Policy'),('type', 'Vendor type'), ('status', 'Status'),
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
        notes.append('Opening net dues + billed + penalty accrued in period − cash received − security applied = closing net dues. Negative dues represent credits.')
    if kind=='estate':
        notes.append('Total due combines open bill principal, interest and one-off charges. The security column totals the deposit still held. A term filter includes security for its original award. Charge history uses the current assessment and latest recorded waiver decision.')
    notes.append('Cash receipts exclude security applications. Principal and interest settled include both sources; held security is a separate liability.')
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
