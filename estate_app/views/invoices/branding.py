import base64
import logging
from pathlib import Path


def invoice_logo_data_uri(system_settings):
    if system_settings and system_settings.letterhead_logo:
        try:
            logo = system_settings.letterhead_logo
            with logo.open('rb') as image:
                content = image.read()
            extension = Path(logo.name).suffix.lower()
            mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}[extension]
            return f'data:{mime};base64,' + base64.b64encode(content).decode('ascii')
        except (OSError, ValueError, KeyError):
            logging.getLogger(__name__).warning('Invoice logo unavailable; using the generic application logo.')
    content = (Path(__file__).resolve().parents[2] / 'static' / 'estate_app' / 'invoice-logo.png').read_bytes()
    return 'data:image/png;base64,' + base64.b64encode(content).decode('ascii')


def invoice_branding_context(system_settings, year):
    return {
        'invoice_settings': system_settings,
        'invoice_logo': invoice_logo_data_uri(system_settings),
        'reference_placeholder': system_settings.reference_number_format.replace('{year}', str(year)),
    }


def invoice_configuration_error(request):
    from django.http import JsonResponse
    from django.shortcuts import render
    from ...models import SystemSettings
    if SystemSettings.get_settings().letterhead_name.strip():
        return None
    message='Configure the organisation name in Admin System Settings before printing invoices.'
    if request.path.startswith('/api/'):
        return JsonResponse({'error':message},status=400)
    return render(request,'invoice_setup_required.html',{'message':message},status=400)
