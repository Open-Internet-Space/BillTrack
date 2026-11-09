from ...models import Bill, SystemSettings
from .context import consolidated_invoice_context
from .context import invoice_context


def selected_bills_from_ids(selected_ids):
    bills = list(
        Bill.objects.filter(pk__in=selected_ids)
        .select_related('tenant', 'created_by')
        .prefetch_related('payments')
    )
    bills_by_id = {bill.pk: bill for bill in bills}
    return [bills_by_id[pk] for pk in selected_ids if pk in bills_by_id]


def selected_invoice_contexts(bills):
    system_settings = SystemSettings.get_settings()
    by_tenant = {}
    for bill in bills:
        group = by_tenant.setdefault(bill.tenant_id, {})
        group[bill.pk] = bill
    invoices = []
    for group in by_tenant.values():
        tenant_bills = list(group.values())
        consolidated = len(tenant_bills) > 1
        context = (consolidated_invoice_context(tenant_bills, system_settings) if consolidated
                   else invoice_context(tenant_bills[0], system_settings))
        invoices.append({'invoice': context, 'consolidated': consolidated})
    return invoices
