"""Shared, conservative reminder selection and SMTP delivery."""
import calendar
import datetime as dt
import hashlib
import json
import smtplib
from collections import Counter
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.db.models import F, Q
from django.db import transaction
from django.utils import timezone
from ..models import Bill
from ..models.reminders import ReminderSettings, ReminderDelivery, ReminderSubmission
from ..views.bills import bill_read_queryset
from .delivery import send_message, PartialRecipientAcceptance
from .locking import submission_lock

OFFSETS=(-1,0,1,7,14,26)
BLOCKING=('preparing','sending','accepted','review')

def cutoff_date(receipt):
    month=receipt.month+3
    year=receipt.year+(month-1)//12
    month=(month-1)%12+1
    return dt.date(year,month,min(receipt.day,calendar.monthrange(year,month)[1]))

def milestone(receipt,due,today):
    if not receipt or today>cutoff_date(receipt):
        return None
    elapsed=min((today-due).days,(cutoff_date(receipt)-due).days)
    if elapsed>=41:
        offset=41+15*((elapsed-41)//15)
    else:
        eligible=[offset for offset in OFFSETS if offset<=elapsed]
        if not eligible:
            return None
        offset=eligible[-1]
    return offset,due+dt.timedelta(days=offset)

def smtp_fingerprint():
    values=[getattr(settings,key,'') for key in ('EMAIL_BACKEND','EMAIL_HOST','EMAIL_PORT','EMAIL_HOST_USER',
            'EMAIL_HOST_PASSWORD','EMAIL_USE_TLS','EMAIL_USE_SSL','DEFAULT_FROM_EMAIL')]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()

def mail_configured():
    return bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD and settings.DEFAULT_FROM_EMAIL)

def preview(today=None,ignore_log_pk=None):
    today=today or timezone.localdate()
    # A three-calendar-month window is at most 92 days; retain a margin for boundary dates.
    history=ReminderSubmission.objects.filter(send_date__gte=today-dt.timedelta(days=100),status__in=BLOCKING)
    if ignore_log_pk:
        history=history.exclude(pk=ignore_log_pk)
    blocked=set();linked_legacy_blocked=set();blocked_today=set()
    for log in history:
        for item in log.items:
            if not isinstance(item, dict):
                continue
            history_key = item.get('key')
            if isinstance(history_key, str) and history_key.count('|') == 5 and item.get('bill_id'):
                linked_legacy_blocked.add((history_key, item['bill_id']))
            else:
                blocked.add(history_key)
        if log.send_date==today:
            blocked_today.add(str(log.allottee_uuid))
    skipped=Counter()
    oldest=today-dt.timedelta(days=100)
    skipped['Receipt not confirmed']=Bill.objects.filter(billing_policy='legacy_receipt',issue_date__isnull=True).count()
    skipped['Email dispatch pending']=Bill.objects.filter(billing_policy='notices_368_369',email_dispatched_at__isnull=True).count()
    skipped['Outside reminder window']=Bill.objects.filter(Q(issue_date__lt=oldest)|Q(email_dispatched_at__date__lt=oldest)).count()
    groups={}
    for bill in bill_read_queryset().filter(Q(issue_date__gte=oldest)|Q(email_dispatched_at__date__gte=oldest)):
        tenant=bill.tenant
        if not tenant.active:
            skipped['Inactive allottee']+=1;continue
        email=tenant.email.strip()
        try:
            if not email or tenant.email_not_provided:
                raise ValidationError('Missing email')
            validate_email(email)
        except ValidationError:
            skipped['Missing or invalid email']+=1;continue
        confirmed=bill.confirmation_date
        if confirmed>today:
            continue
        if today>cutoff_date(confirmed):
            skipped['Outside reminder window']+=1;continue
        stage=milestone(confirmed,bill.due_date,today)
        if stage is None:
            skipped['No reminder due yet']+=1;continue
        principal=bill.balance_due;penalty=bill.penalty
        if principal+penalty<=0:
            skipped['Settled bill']+=1;continue
        offset,scheduled=stage
        key='|'.join([str(tenant.uuid),str(bill.year),str(bill.month),str(confirmed),str(bill.due_date),str(offset)])
        legacy_key = key
        if bill.allotment_id:
            key += '|' + str(bill.allotment.uuid)
        if key in blocked or (legacy_key, bill.pk) in linked_legacy_blocked or str(tenant.uuid) in blocked_today:
            skipped['Already sent or awaiting review']+=1;continue
        group=groups.setdefault(str(tenant.uuid),{'uuid':str(tenant.uuid),'allottee':tenant,'email':email,'items':[],'total':Decimal('0')})
        group['items'].append({'key':key,'bill_id':bill.pk,'reference':bill.dispatch_ref_no or bill.invoice_no,
            'period':f'{bill.get_month_name()} {bill.year}','receipt_date':str(confirmed),'due_date':str(bill.due_date),
            'shop':bill.allotment.shop.code if bill.allotment_id else '', 'award':bill.allotment.award_reference if bill.allotment_id else '',
            'policy':bill.billing_policy,
            'offset':offset,'scheduled_date':str(scheduled),'principal':f'{principal:.2f}','penalty':f'{penalty:.2f}',
            'total':f'{principal+penalty:.2f}'})
        group['total']+=principal+penalty
    return sorted(groups.values(),key=lambda group:group['allottee'].name.casefold()),dict(skipped)

def safe_error(error):
    if isinstance(error,smtplib.SMTPAuthenticationError):
        return 'Mail sign-in failed. Check the sender address and app password.'
    if isinstance(error,(smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused)):
        return 'The mail server refused the sender or recipient address.'
    if isinstance(error,smtplib.SMTPDataError):
        return 'The mail server rejected this message. Review mailbox policy or limits.'
    return 'Mail connection or submission failed. Check SMTP settings and network access; private server details were not logged.'

def send_test(address):
    from .composition import validate_sender
    validate_sender()
    validate_email(address)
    if not mail_configured():
        raise ValidationError('Configure the Gmail SMTP sender and app password in the private .env first.')
    connection=get_connection(fail_silently=False)
    try:
        connection.open()
        message=EmailMessage('BillTrack email setup test','This is a BillTrack email configuration test. No allottee or billing data is included.',
                             settings.DEFAULT_FROM_EMAIL,[address],connection=connection)
        if message.send()!=1:
            raise ValidationError('The test message was not accepted by the mail server.')
    finally:
        connection.close()
    config,_=ReminderSettings.objects.get_or_create(pk=1)
    config.verified_config=smtp_fingerprint();config.save(update_fields=['verified_config','updated_at'])

def send_reminders(today=None,selected=None,automatic=False,confirmed=None,user_id=None):
    today=today or timezone.localdate()
    result={'accepted':0,'failed':0,'review':0,'skipped':0}
    if automatic or confirmed is None:
        result['error']='Reminder emails require a preview and confirmation in Admin; automatic and direct sending are disabled.'
        return result
    from .composition import confirmed_messages, group_fingerprint
    approved=confirmed_messages(confirmed,user_id,today)
    groups,_=preview(today)
    groups=[group for group in groups if group['uuid'] in approved]
    for group in groups:
        with transaction.atomic():
            claimed=ReminderSubmission.objects.filter(allottee_uuid=group['uuid'],send_date=today,
                status__in=['failed','skipped']).update(status='preparing',attempts=F('attempts')+1,error='')
            log,created=ReminderSubmission.objects.get_or_create(allottee_uuid=group['uuid'],send_date=today,defaults={
                'allottee_name':group['allottee'].name,'recipient':approved[group['uuid']]['to'],'items':group['items']})
            if not created and not claimed:
                result['skipped']+=1;continue
            delivery,_=ReminderDelivery.objects.get_or_create(allottee_uuid=group['uuid'],send_date=today,defaults={
                'allottee':group['allottee'],'allottee_name':log.allottee_name,'recipient':log.recipient,'items':log.items})
            log.delivery_id=delivery.pk
            log.message={key:approved[group['uuid']][key] for key in ('to','cc','subject','body')}
            save_submission(log)
        with submission_lock(log.pk):
            # Re-read after claiming; do not hold a database transaction during network calls.
            fresh=next((g for g in preview(today,ignore_log_pk=log.pk)[0] if g['uuid']==group['uuid']),None)
            if fresh is None or group_fingerprint(fresh,today)!=approved[group['uuid']]['fingerprint']:
                log.status='skipped';log.error='Reminder details changed after preview. Prepare and confirm a new preview.';save_submission(log)
                result['skipped']+=1;continue
            log.items=fresh['items'];log.recipient=approved[group['uuid']]['to'];log.allottee_name=fresh['allottee'].name;save_submission(log)
            if not mail_configured():
                log.status='failed';log.error='SMTP sender/app password is not configured.';save_submission(log)
                result['failed']+=1;break
            connection=get_connection(fail_silently=False)
            try:
                connection.open()
            except Exception as error:
                log.status='failed';log.error=safe_error(error);save_submission(log)
                result['failed']+=1;break
            try:
                content=approved[group['uuid']]
                cc=[address.strip() for address in content['cc'].replace(';',',').split(',') if address.strip()]
                message=EmailMessage(content['subject'],content['body'],settings.DEFAULT_FROM_EMAIL,[log.recipient],cc=cc,connection=connection)
                log.status='sending';save_submission(log)
                try:
                    count=send_message(message,connection)
                except PartialRecipientAcceptance:
                    log.status='review';log.error='Some recipients were refused; others may already have received the message. Check provider activity before permitting another attempt.'
                except (smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPDataError) as error:
                    log.status='failed';log.error=safe_error(error)
                except Exception:
                    log.status='review';log.error='Submission may have reached the mail server. Check provider activity before permitting another attempt.'
                else:
                    log.status='accepted' if count==1 else 'review'
                    log.error='' if count==1 else 'The backend did not confirm acceptance. Check provider activity before retrying.'
                save_submission(log)
                result[{'accepted':'accepted','failed':'failed','review':'review'}[log.status]]+=1
            finally:
                try:connection.close()
                except Exception:pass
    return result


@transaction.atomic
def save_submission(log):
    """Persist protected evidence and visible history together, without recreating deleted history."""
    expected = getattr(log, '_expected_status', log.status)
    log.updated_at = timezone.now()
    values = {key:getattr(log,key) for key in ('delivery_id','message','allottee_name','recipient','items','status','error','reviewed_by','updated_at')}
    if not ReminderSubmission.objects.filter(pk=log.pk,attempts=log.attempts,status=expected).update(**values):
        raise ValidationError('This submission changed after it was claimed. Stop and review the current protected sending state.')
    log._expected_status = log.status
    ReminderDelivery.objects.filter(pk=log.delivery_id,allottee_uuid=log.allottee_uuid,send_date=log.send_date).update(
        **{key:getattr(log,key) for key in ('allottee_name','recipient','items','status','attempts','error','reviewed_by','updated_at')})
