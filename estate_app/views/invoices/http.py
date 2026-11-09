from functools import wraps
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from weasyprint import HTML
from ...account_security.authentication import AccountTokenAuthentication as TokenAuthentication
from ...account_security.service import permitted
from rest_framework.exceptions import AuthenticationFailed
from django.views.decorators.http import require_GET
from ...models import Bill
from .context import invoice_context
from .selection import selected_bills_from_ids
from .selection import selected_invoice_contexts


def authenticated_invoice(view):
    @wraps(view)
    def protected(request, *args, **kwargs):
        if not (request.user.is_authenticated and permitted(request.user)):
            try:
                credentials = TokenAuthentication().authenticate(request)
            except AuthenticationFailed:
                credentials = None
            if not credentials:
                response = JsonResponse({'detail': 'Sign in to view invoices.'}, status=401)
                response['WWW-Authenticate'] = 'Token'
                response['Cache-Control'] = 'no-store'
                return response
            request.user, request.auth = credentials
        from .branding import invoice_configuration_error
        response = invoice_configuration_error(request)
        if response is None:
            response = view(request, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response
    return protected


@require_GET
@authenticated_invoice
def invoice_view(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    html_string = render_to_string('invoice_format2.html', invoice_context(bill))

    if request.GET.get('format') == 'pdf':
        pdf = HTML(
            string=html_string,
            base_url=request.build_absolute_uri()
        ).write_pdf()

        invoice_no = (bill.invoice_no or f"bill-{bill.id}").replace('/', '-')
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice-format-2-{invoice_no}.pdf"'
        return response

    return HttpResponse(html_string)


invoice_format2_view = invoice_view


@require_GET
@authenticated_invoice
def bulk_invoice_view(request):
    raw_ids = request.GET.get('ids', '')
    try:
        selected_ids = [int(pk) for pk in raw_ids.split(',') if pk.strip()]
    except ValueError:
        selected_ids = []

    ordered_bills = selected_bills_from_ids(selected_ids)
    html_string = render_to_string('bulk_invoice.html', {
        'print_invoices': selected_invoice_contexts(ordered_bills),
        'title': 'Print selected bills',
    })

    if request.GET.get('format') == 'pdf':
        pdf = HTML(
            string=html_string,
            base_url=request.build_absolute_uri()
        ).write_pdf()
        return HttpResponse(pdf, content_type='application/pdf')

    return HttpResponse(html_string)
