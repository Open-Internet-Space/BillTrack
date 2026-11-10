from ..activity.admin import CorrectionAdminMixin
import smtplib
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.conf import settings
from .composition import TemplateSelectionForm, EmailPreviewFormSet, prepare_messages
from django.views.decorators.http import require_http_methods
from ..models.reminders import ReminderSettings, ReminderDelivery
from ..admin_pagination import PaginationAdminMixin
from .service import preview, send_reminders, send_test, smtp_fingerprint, mail_configured, safe_error
from ..activity.admin import ReasonForm, apply_reason
from ..models import ReminderSubmission
from .service import save_submission
from .locking import submission_lock
from django.db import transaction

@admin.register(ReminderSettings)
class ReminderSettingsAdmin(CorrectionAdminMixin, PaginationAdminMixin,admin.ModelAdmin):
    fields=['automatic_enabled','updated_at']
    readonly_fields=['automatic_enabled','updated_at']
    def has_module_permission(self,request):return request.user.is_superuser
    def has_view_permission(self,request,obj=None):return request.user.is_superuser
    def has_change_permission(self,request,obj=None):return request.user.is_superuser
    def has_add_permission(self,request):return request.user.is_superuser and not ReminderSettings.objects.exists()
    def has_delete_permission(self,request,obj=None):return request.user.is_superuser

@admin.register(ReminderDelivery)
class ReminderDeliveryAdmin(CorrectionAdminMixin, PaginationAdminMixin,admin.ModelAdmin):
    list_display=['send_date','allottee_name','recipient','status','attempts','error']
    list_filter=['status','send_date']
    search_fields=['allottee_name','recipient']
    readonly_fields=['allottee_uuid','created_at','updated_at','attempts']
    def has_module_permission(self,request):return request.user.is_superuser
    def has_view_permission(self,request,obj=None):return request.user.is_superuser
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return request.user.is_superuser
    def has_delete_permission(self,request,obj=None):return request.user.is_superuser

class TestMailForm(forms.Form):
    address=forms.EmailField(label='Your test mailbox')

@require_http_methods(['GET','POST'])
def reminder_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    config=ReminderSettings.objects.filter(pk=1).first() or ReminderSettings(pk=1)
    form=TestMailForm()
    template_form=TemplateSelectionForm()
    preview_forms=None
    preview_error=''
    if request.method=='POST':
        action=request.POST.get('action')
        try:
            if action=='test':
                form=TestMailForm(request.POST)
                if form.is_valid():
                    try:send_test(form.cleaned_data['address'])
                    except (ValidationError,smtplib.SMTPException,OSError) as error:
                        text=' '.join(error.messages) if isinstance(error,ValidationError) else safe_error(error)
                        messages.error(request,text)
                    else:
                        messages.success(request,'Test accepted by the mail server. Verify arrival in your mailbox.')
                        return redirect('admin-email-reminders')
            elif action=='prepare':
                template_form=TemplateSelectionForm(request.POST)
                if template_form.is_valid():
                    prepared=prepare_messages(set(request.POST.getlist('allottee')),template_form.cleaned_data['template'],request.user.pk)
                    preview_forms=EmailPreviewFormSet(initial=prepared,prefix='emails')
            elif action=='confirm_send':
                preview_forms=EmailPreviewFormSet(request.POST,prefix='emails')
                if preview_forms.is_valid():
                    try:
                        result=send_reminders(confirmed=preview_forms.cleaned_data,user_id=request.user.pk)
                    except ValidationError as error:
                        preview_error=' '.join(error.messages)
                    else:
                        messages.info(request,f"Mail server accepted: {result['accepted']}. Failed: {result['failed']}. Needs review: {result['review']}. Skipped: {result['skipped']}.")
                        if result['failed'] or result['review'] or result['skipped']:
                            preview_error='Some messages need attention. Your edits are kept here; copy any wording you need and check delivery history before retrying or preparing a new preview.'
                        else:
                            return redirect('admin-email-reminders')
            elif action in ('send','mode'):
                messages.error(request,'Reminder emails now require an editable preview and confirmation. Automatic sending is disabled.')
            elif action=='release' and request.POST.get('confirmed_not_sent')=='on':
                reason_form=ReasonForm(request.POST)
                if not reason_form.is_valid():
                    raise ValidationError('Enter a written reason for releasing this submission.')
                submission_id=forms.IntegerField(min_value=1).clean(request.POST.get('submission'))
                with submission_lock(submission_id), transaction.atomic():
                    apply_reason(reason_form.cleaned_data['change_reason'])
                    count=ReminderSubmission.objects.filter(pk=submission_id,status__in=['preparing','sending','review']).update(
                        status='failed',error='Administrator checked provider activity and confirmed no message was sent.',
                        reviewed_by=request.user.get_username(),updated_at=timezone.now())
                    if count:
                        save_submission(ReminderSubmission.objects.get(pk=submission_id))
                messages.info(request,'Review recorded; preview again before retrying.' if count else 'No uncertain delivery was changed.')
                return redirect('admin-email-reminders')
            else:
                messages.error(request,'Choose a valid action. Uncertain mail needs explicit confirmation before retrying.')
        except ValidationError as error:
            messages.error(request,' '.join(error.messages))
        except DatabaseError:
            messages.error(request,'The database is busy or a result could not be saved. Check delivery history before retrying; some mail may already have been accepted.')
    if preview_forms is not None:
        return TemplateResponse(request,'admin/email_reminder_preview.html',{**admin.site.each_context(request),
            'title':'Review emails before sending','preview_forms':preview_forms,'preview_error':preview_error,'from_email':settings.DEFAULT_FROM_EMAIL})
    groups,skipped=preview()
    context={**admin.site.each_context(request),'title':'Email reminders','config':config,
       'configured':mail_configured(),'verified':bool(config.verified_config and config.verified_config==smtp_fingerprint()),
       'groups':groups,'skipped':skipped,'test_form':form,'template_form':template_form,
       'recent':ReminderDelivery.objects.all()[:30],
       'uncertain':ReminderSubmission.objects.filter(status__in=['preparing','sending','review'])[:30]}
    return TemplateResponse(request,'admin/email_reminders.html',context)
