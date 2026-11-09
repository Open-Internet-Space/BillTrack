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
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone
from ..models import Bill
from ..models.reminders import ReminderSettings, ReminderDelivery
from ..views.bills import bill_read_queryset

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
    history=ReminderDelivery.objects.filter(send_date__gte=today-dt.timedelta(days=100),status__in=BLOCKING)
    if ignore_log_pk:
        history=history.exclude(pk=ignore_log_pk)
    blocked=set();blocked_today=set()
    for log in history:
        blocked.update(item.get('key') for item in log.items if isinstance(item,dict))
        if log.send_date==today:
            blocked_today.add(str(log.allottee_uuid))
    skipped=Counter()
    skipped['Receipt not confirmed']=Bill.objects.filter(issue_date__isnull=True).count()
    skipped['Outside reminder window']=Bill.objects.filter(issue_date__lt=today-dt.timedelta(days=100)).count()
    groups={}
    for bill in bill_read_queryset().filter(issue_date__isnull=False,issue_date__gte=today-dt.timedelta(days=100)):
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
        if today>cutoff_date(bill.issue_date):
            skipped['Outside reminder window']+=1;continue
        stage=milestone(bill.issue_date,bill.due_date,today)
        if stage is None:
            skipped['No reminder due yet']+=1;continue
        principal=bill.balance_due;penalty=bill.penalty
        if principal+penalty<=0:
            skipped['Settled bill']+=1;continue
        offset,scheduled=stage
        key='|'.join([str(tenant.uuid),str(bill.year),str(bill.month),str(bill.issue_date),str(bill.due_date),str(offset)])
        if key in blocked or str(tenant.uuid) in blocked_today:
            skipped['Already sent or awaiting review']+=1;continue
        group=groups.setdefault(str(tenant.uuid),{'uuid':str(tenant.uuid),'allottee':tenant,'email':email,'items':[],'total':Decimal('0')})
        group['items'].append({'key':key,'bill_id':bill.pk,'reference':bill.dispatch_ref_no or bill.invoice_no,
            'period':f'{bill.get_month_name()} {bill.year}','receipt_date':str(bill.issue_date),'due_date':str(bill.due_date),
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

def send_reminders(today=None,selected=None,automatic=False):
    today=today or timezone.localdate()
    result={'accepted':0,'failed':0,'review':0,'skipped':0}
    if automatic:
        config=ReminderSettings.objects.filter(pk=1).first()
        if not config or not config.automatic_enabled:
            return result
        if not mail_configured() or config.verified_config!=smtp_fingerprint():
            result['error']='Automatic sending paused: verify the current SMTP configuration with a test email.'
            return result
    groups,_=preview(today)
    if selected is not None:
        groups=[group for group in groups if group['uuid'] in selected]
    for group in groups:
        log,created=ReminderDelivery.objects.get_or_create(allottee_uuid=group['uuid'],send_date=today,defaults={
            'allottee':group['allottee'],'allottee_name':group['allottee'].name,'recipient':group['email'],'items':group['items']})
        if not created:
            claimed=ReminderDelivery.objects.filter(pk=log.pk,status__in=['failed','skipped']).update(status='preparing',attempts=F('attempts')+1,error='')
            if not claimed:
                result['skipped']+=1;continue
            log.refresh_from_db()
        # Re-read after claiming; do not hold a database transaction during network calls.
        fresh=next((g for g in preview(today,ignore_log_pk=log.pk)[0] if g['uuid']==group['uuid']),None)
        if fresh is None:
            log.status='skipped';log.error='No eligible balances remained after the final recheck.';log.save()
            result['skipped']+=1;continue
        log.items=fresh['items'];log.recipient=fresh['email'];log.allottee_name=fresh['allottee'].name;log.save()
        if not mail_configured():
            log.status='failed';log.error='SMTP sender/app password is not configured.';log.save()
            result['failed']+=1;break
        connection=get_connection(fail_silently=False)
        try:
            connection.open()
        except Exception as error:
            log.status='failed';log.error=safe_error(error);log.save()
            result['failed']+=1;break
        try:
            body=render_to_string('reminders/email.txt',{'group':fresh,'today':today})
            message=EmailMessage('BillTrack payment reminder',body,settings.DEFAULT_FROM_EMAIL,[log.recipient],connection=connection)
            log.status='sending';log.save(update_fields=['status','updated_at'])
            try:
                count=message.send()
            except (smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPDataError) as error:
                log.status='failed';log.error=safe_error(error)
            except Exception:
                log.status='review';log.error='Submission may have reached the mail server. Check provider activity before permitting another attempt.'
            else:
                log.status='accepted' if count==1 else 'review'
                log.error='' if count==1 else 'The backend did not confirm acceptance. Check provider activity before retrying.'
            log.save(update_fields=['status','error','updated_at'])
            result[{'accepted':'accepted','failed':'failed','review':'review'}[log.status]]+=1
        finally:
            try:connection.close()
            except Exception:pass
    return result
