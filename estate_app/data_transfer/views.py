import json
import uuid
from pathlib import Path
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from .serialization import MAX_IMPORT_SIZE, MODELS
from .serialization import export_bytes
from .restoration import restore_data
from .serialization import validate_data
from ..activity.admin import ReasonForm
from ..activity.context import operation
from ..activity.deletion import deletion_plan, confirmed
from ..models import Tenant, SystemSettings


class ImportForm(ReasonForm):
    file = forms.FileField(label='BillTrack data export (.json)', widget=forms.FileInput(attrs={'accept': '.json'}))
    mode = forms.ChoiceField(label='Import mode', choices=[
        ('replace', '1. Replace all data and settings'), ('merge', '2. Merge into existing data'),
    ], widget=forms.RadioSelect, initial='merge')
    confirm = forms.BooleanField(label='I understand that Replace removes current estate records, billing data and settings.',
                                 required=False)

    def clean_file(self):
        upload = self.cleaned_data['file']
        if upload.size > MAX_IMPORT_SIZE:
            raise ValidationError('Choose an export smaller than 25 MB.')
        try:
            data = json.load(upload)
            self.objects, self.logo = validate_data(data)
        except ValidationError as error:
            raise ValidationError(error.messages) from error
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ValidationError('The file is not valid BillTrack JSON.') from error
        return upload

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('mode') == 'replace' and not cleaned.get('confirm'):
            self.add_error('confirm', 'Confirm replacement before importing, or choose Merge.')
        return cleaned


def check_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied


def replacement_plan():
    return deletion_plan([obj for model in MODELS for obj in model.objects.order_by('pk')])


@require_GET
def export_view(request):
    check_superuser(request)
    with transaction.atomic():
        content = export_bytes()
    response = HttpResponse(content, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="billtrack-data-{timezone.now():%Y%m%dT%H%M%SZ}.json"'
    return response


@require_http_methods(['GET', 'POST'])
def transfer_view(request):
    check_superuser(request)
    form = ImportForm(request.POST or None, request.FILES or None)
    plan = replacement_plan()
    if request.method == 'POST' and form.is_valid():
        try:
            backup_id = uuid.uuid4()
            folder = Path(settings.BASE_DIR) / 'backups' / 'admin-imports'
            folder.mkdir(parents=True, exist_ok=True)
            with operation(actor=request.user, source='import', reason=form.cleaned_data['change_reason']), transaction.atomic():
                if form.cleaned_data['mode'] == 'replace' and not confirmed(request.POST.get('confirmation'),
                        replacement_plan()):
                    raise ValidationError('Review the current replacement effects, select the file again and confirm before replacing records.')
                # Keep the safety export private, and finish writing it before any deletion.
                with (folder / f'{backup_id}.json').open('xb') as stream:
                    stream.write(export_bytes())
                counts = restore_data(form.objects, form.logo, form.cleaned_data['mode'])
            request.session['data_transfer_backup'] = str(backup_id)
            messages.success(request, f'Import completed: {counts["added"]} records imported; {counts["kept"]} existing records kept.')
            return redirect('admin-data-transfer')
        except (ValidationError, DatabaseError, OSError) as error:
            message = (' '.join(error.messages) if isinstance(error, ValidationError)
                       else 'Import failed. Check for conflicting invoice numbers or unavailable backup/media storage. No data was changed.')
            form.add_error(None, message)
    backup_id = request.session.get('data_transfer_backup')
    return TemplateResponse(request, 'admin/data_transfer.html', {
        **admin.site.each_context(request), 'title': 'Export / import data and settings', 'form': form,
        'backup_url': reverse('admin-data-transfer-backup', args=[backup_id]) if backup_id else None,
        'replacement_plan': plan,
    })


@require_GET
def backup_view(request, backup_id):
    check_superuser(request)
    target = Path(settings.BASE_DIR) / 'backups' / 'admin-imports' / f'{backup_id}.json'
    try:
        return FileResponse(target.open('rb'), as_attachment=True, filename=f'billtrack-before-import-{backup_id}.json')
    except FileNotFoundError as error:
        raise Http404 from error
