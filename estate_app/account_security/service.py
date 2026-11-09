import hashlib
import logging
import secrets
import smtplib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import BoundedSemaphore

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.authtoken.models import Token

from ..models import AccountAccess, AccountRateLimit, EmailChallenge, ReminderSettings

_mail_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix='account-recovery-mail')
_mail_slots = BoundedSemaphore(20)
logger = logging.getLogger(__name__)


class AccountError(Exception):
    pass


class RateLimitError(AccountError):
    def __init__(self, retry_after):
        super().__init__('Too many attempts. Please try again later.')
        self.retry_after = retry_after


def canonical_email(value):
    value = value.strip().casefold()
    validate_email(value)
    if len(value) > 254:
        raise ValidationError('Enter an email address of at most 254 characters.')
    return value


def available():
    from ..reminders.service import mail_configured, smtp_fingerprint
    return (settings.ACCOUNT_EMAIL_ENABLED and mail_configured()
            and ReminderSettings.objects.filter(pk=1, verified_config=smtp_fingerprint()).exists())


def permitted(user):
    if not user or not user.is_active:
        return False
    return not AccountAccess.objects.filter(user=user).exclude(status='approved').exists()


def email_owner(email):
    users = list(get_user_model().objects.filter(email__iexact=email)[:2])
    if len(users) != 1:
        return None
    user = users[0]
    if get_user_model().objects.filter(username__iexact=email).exclude(pk=user.pk).exists():
        return None
    if AccountAccess.objects.filter(verified_email=email).exclude(user=user).exists():
        return None
    return user


def find_user(identifier):
    users = list(get_user_model().objects.filter(username=identifier)[:2])
    user = users[0] if len(users) == 1 else email_owner(identifier.strip().casefold())
    if user and '@' in identifier and get_user_model().objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)).exclude(pk=user.pk).exists():
        return None
    return user


def limit(scope, identity, maximum, seconds):
    now = int(time.time())
    key = hashlib.sha256((scope + ':' + identity).encode()).hexdigest()
    AccountRateLimit.objects.get_or_create(key=key, defaults={'started': now})
    rows = AccountRateLimit.objects.filter(pk=key)
    rows.filter(started__lte=now - seconds).update(started=now, attempts=0)
    if not rows.filter(attempts__lt=maximum).update(attempts=F('attempts') + 1):
        raise RateLimitError(max(1, rows.get().started + seconds - now))


def send_budget(email, address):
    now = int(time.time())
    AccountRateLimit.objects.filter(started__lt=now - 86400).delete()
    EmailChallenge.objects.filter(expires_at__lt=now - 86400).delete()
    expire_applications()
    limit('send-ip', address, 20, 3600)
    limit('send-global', 'installation', 100, 3600)
    limit('send-hour', email, 5, 3600)
    limit('send-minute', email, 1, 60)


def password_stamp(user):
    return salted_hmac('account-password', user.password).hexdigest()


def expire_applications():
    now = timezone.now()
    with transaction.atomic():
        expired = AccountAccess.objects.filter(status='pending', verified_at__isnull=True,
                    signup_email__isnull=False, user__is_active=False, user__date_joined__lt=now-timedelta(days=1))
        if expired.update(status='rejected', signup_email=None, decided_at=now):
            ids = list(AccountAccess.objects.filter(status='rejected', signup_email__isnull=True,
                       verified_at__isnull=True, decided_at=now).values_list('user_id', flat=True))
            # Keep the account row/history while releasing an unverified address after 24 hours.
            get_user_model().objects.filter(pk__in=ids).update(email='', password='!')
            EmailChallenge.objects.filter(user_id__in=ids).update(consumed=True)


def deliver(email, code, purpose):
    labels = {'signup': 'verify your signup email', 'verify': 'verify your account email', 'recovery': 'reset your password'}
    try:
        sent = send_mail('BillTrack verification code',
                         f'Your BillTrack code is {code}. Use it to {labels[purpose]}.\n'
                         'It expires in 10 minutes. Never share this code.\n'
                         'If you did not request this, ignore this message.',
                         settings.DEFAULT_FROM_EMAIL, [email])
        if sent != 1:
            raise OSError('Submission was not accepted')
    except (OSError, smtplib.SMTPException):
        raise AccountError('The email could not be submitted. Please try again later.') from None


def queue_recovery_mail(email, code, purpose):
    # Keep SMTP latency out of recovery responses; the bounded queue holds codes only in memory.
    if not _mail_slots.acquire(blocking=False):
        logger.warning('Account recovery email queue is full; request a new code later.')
        return
    def work():
        try:
            deliver(email, code, purpose)
        except AccountError:
            logger.warning('Account recovery email submission failed. Check SMTP configuration.')
        finally:
            _mail_slots.release()
    try:
        _mail_workers.submit(work)
    except RuntimeError:
        _mail_slots.release()
        logger.warning('Account recovery email worker is stopping; request a new code later.')


def issue(purpose, email, user):
    now = int(time.time())
    key = hashlib.sha256((purpose + ':' + email).encode()).hexdigest()
    nonce = uuid.uuid4()
    code = f'{secrets.randbelow(1000000):06d}'
    digest = salted_hmac('email-otp', str(nonce) + ':' + code, algorithm='sha256').hexdigest()
    EmailChallenge.objects.update_or_create(key=key, defaults={
        'nonce': nonce, 'user': user, 'purpose': purpose, 'email': email,
        'digest': digest, 'password_stamp': password_stamp(user) if user else '',
        'expires_at': now + 600, 'consumed': False,
    })
    if user:
        try:
            if purpose == 'recovery':
                queue_recovery_mail(email, code, purpose)
            else:
                deliver(email, code, purpose)
        except AccountError:
            EmailChallenge.objects.filter(key=key, nonce=nonce).update(consumed=True)
            raise AccountError('The email could not be submitted. Please try again later.') from None
    return str(nonce)


def verification_budget(nonce, purpose):
    try:
        challenge = EmailChallenge.objects.filter(nonce=uuid.UUID(str(nonce)), purpose=purpose).first()
    except (ValueError, TypeError):
        challenge = None
    if challenge:
        limit('verify', challenge.email, 5, 900)


def consume(nonce, purpose, code, password=None):
    try:
        challenge = EmailChallenge.objects.filter(nonce=uuid.UUID(str(nonce)), purpose=purpose).first()
    except (ValueError, TypeError):
        challenge = None
    if not challenge:
        raise AccountError('The code is invalid or expired. Request a new code.')
    digest = salted_hmac('email-otp', str(challenge.nonce) + ':' + code, algorithm='sha256').hexdigest()
    user = challenge.user
    if (not user or len(code) != 6 or not code.isascii() or not code.isdigit()
            or not constant_time_compare(digest, challenge.digest)
            or challenge.email != user.email.strip().casefold()
            or email_owner(challenge.email) != user
            or not constant_time_compare(challenge.password_stamp, password_stamp(user))):
        raise AccountError('The code is invalid or expired. Request a new code.')
    if purpose != 'signup' and not permitted(user):
        raise AccountError('The code is invalid or expired. Request a new code.')
    if purpose == 'signup' and not AccountAccess.objects.filter(user=user, status='pending').exists():
        raise AccountError('The code is invalid or expired. Request a new code.')
    if purpose == 'recovery':
        if password is None:
            raise AccountError('Enter a new password.')
        validate_password(password, user)
    with transaction.atomic():
        # Claim is the first SQL statement: SQLite must acquire its write lock before reads.
        if not EmailChallenge.objects.filter(pk=challenge.pk, nonce=challenge.nonce, consumed=False,
                                             expires_at__gt=int(time.time())).update(consumed=True):
            raise AccountError('The code is invalid or expired. Request a new code.')
        user.refresh_from_db()
        if (challenge.email != user.email.strip().casefold() or email_owner(challenge.email) != user
                or not constant_time_compare(challenge.password_stamp, password_stamp(user))
                or (purpose != 'signup' and not permitted(user))
                or (purpose == 'signup' and not AccountAccess.objects.filter(user=user, status='pending').exists())):
            raise AccountError('The code is invalid or expired. Request a new code.')
        if purpose == 'recovery':
            change_password(user, password)
        else:
            mark_verified(user, challenge.email)
    return user, challenge.email


def mark_verified(user, email):
    access, _ = AccountAccess.objects.get_or_create(user=user)
    access.verified_email = email
    access.verified_at = timezone.now()
    access.save(update_fields=['verified_email', 'verified_at'])


def change_password(user, password):
    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()
        EmailChallenge.objects.filter(user=user, consumed=False).update(consumed=True)
    # Django invalidates sessions lazily using the changed password hash.


def decide(access_id, approver, decision):
    if not approver.is_superuser or decision not in ('approve', 'reject'):
        raise AccountError('Only a superuser can approve or reject accounts.')
    with transaction.atomic():
        status = 'approved' if decision == 'approve' else 'rejected'
        if not AccountAccess.objects.filter(pk=access_id, status='pending').update(
                status=status, decided_by=approver, decided_at=timezone.now()):
            raise AccountError('This application has already been decided.')
        access = AccountAccess.objects.select_related('user').get(pk=access_id)
        if decision == 'approve' and (not access.verified_at or access.verified_email != access.user.email.strip().casefold()
                                      or email_owner(access.verified_email) != access.user):
            raise AccountError('Verify a unique email address before approval.')
        get_user_model().objects.filter(pk=access.user_id).update(is_active=decision == 'approve', is_staff=False, is_superuser=False)
        from ..models import UserProfile
        UserProfile.objects.update_or_create(user=access.user, defaults={'role': 'staff'})
