"""Personal authenticator enrollment and one-use recovery, independent of SMTP."""
import base64
import binascii
import hashlib
import hmac
import secrets
import struct
import time

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from ..models import AccountAuthenticator, EmergencyRecoveryState
from . import service
from .forms import CodeForm, ExistingEmailForm


def matching_counter(secret, code):
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    try:
        key = base64.b32decode(secret.strip().upper() + '=' * (-len(secret.strip()) % 8))
    except (binascii.Error, ValueError):
        return None
    counter = int(time.time() // 30)
    for step in (counter - 1, counter, counter + 1):
        if step < 0:
            continue
        digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
        offset = digest[-1] & 15
        value = (struct.unpack('>I', digest[offset:offset+4])[0] & 0x7fffffff) % 1000000
        if constant_time_compare(f'{value:06d}', code):
            return step
    return None


def reset_password(user, code, password, confirmation, legacy_validator, emergency=False):
    if emergency:
        service.limit('superuser-emergency', 'installation', 20, 900)
    if not service.permitted(user):
        return False
    authenticator = AccountAuthenticator.objects.filter(user=user).first()
    counter = matching_counter(authenticator.secret, code) if authenticator and not emergency else None
    use_emergency = emergency or (not authenticator and user.is_staff)
    if not use_emergency and authenticator:
        valid = counter is not None and counter > authenticator.last_counter
    else:
        valid = False
        if use_emergency and settings.TOTP_RESET_SECRET:
            if not emergency:
                service.limit('superuser-emergency', 'installation', 20, 900)
            if legacy_validator(settings.TOTP_RESET_SECRET, code):
                counter = matching_counter(settings.TOTP_RESET_SECRET, code)
                valid = counter is not None
    if not valid:
        return False
    if password != confirmation:
        raise ValidationError('Passwords do not match.', code='mismatch')
    validate_password(password, user)
    if use_emergency:
        EmergencyRecoveryState.objects.get_or_create(pk=1)
    with transaction.atomic():
        if not use_emergency:
            if not AccountAuthenticator.objects.filter(pk=authenticator.pk, secret=authenticator.secret,
                                                        last_counter__lt=counter).update(last_counter=counter):
                return False
            user.refresh_from_db()
            if not service.permitted(user):
                raise service.AccountError('The username or authenticator code is invalid.')
        else:
            if not EmergencyRecoveryState.objects.filter(pk=1, last_counter__lt=counter).update(last_counter=counter):
                return False
            user.refresh_from_db()
            if (not service.permitted(user) or (not emergency and
                    (not user.is_staff or AccountAuthenticator.objects.filter(user=user).exists()))):
                raise service.AccountError('The username or authenticator code is invalid.')
        service.change_password(user, password)
    return True


@never_cache
@require_http_methods(['GET', 'POST'])
def authenticator_setup(request):
    pending = request.session.get('authenticator_setup')
    error, notice = '', ''
    if pending and pending['expires'] <= int(time.time()):
        request.session.pop('authenticator_setup', None)
        pending = None
        error = 'Setup expired. Enter your current password again.'
    form = CodeForm(request.POST or None) if pending else ExistingEmailForm(request.POST or None)
    if pending:
        form.fields['code'].label = 'Authenticator code'
        form.fields['code'].help_text = 'Enter the current code from your authenticator app.'
    if request.method == 'POST':
        try:
            service.limit('totp-setup-ip', request.META.get('REMOTE_ADDR', 'unknown'), 20, 900)
            if pending:
                service.limit('totp-setup-code', str(pending['user']), 5, 900)
                if form.is_valid():
                    user = get_user_model().objects.get(pk=pending['user'])
                    counter = matching_counter(pending['secret'], form.cleaned_data['code'])
                    if counter is None or not service.permitted(user) or not constant_time_compare(pending['stamp'], service.password_stamp(user)):
                        raise service.AccountError('The account or authenticator code is invalid.')
                    with transaction.atomic():
                        # Unique enrollment is the first write; an existing setup cannot be replaced.
                        AccountAuthenticator.objects.create(user=user, secret=pending['secret'], last_counter=counter)
                        user.refresh_from_db()
                        if not service.permitted(user) or not constant_time_compare(pending['stamp'], service.password_stamp(user)):
                            raise service.AccountError('Account changed. Start setup again.')
                    request.session.pop('authenticator_setup', None)
                    pending = None
                    notice = 'Authenticator recovery is ready. Wait for the next code before using recovery. Keep your authenticator app safe.'
            elif form.is_valid():
                candidate = service.find_user(form.cleaned_data['username'])
                service.limit('totp-setup-password', str(candidate.pk) if candidate else form.cleaned_data['username'].casefold(), 5, 900)
                user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
                if not user:
                    raise service.AccountError('Invalid credentials or account not approved.')
                if AccountAuthenticator.objects.filter(user=user).exists():
                    raise service.AccountError('An authenticator is already configured. Contact a superuser if it must be replaced.')
                pending = {'user': user.pk, 'secret': base64.b32encode(secrets.token_bytes(20)).decode(),
                           'stamp': service.password_stamp(user), 'expires': int(time.time())+600,
                           'label': user.email or user.username}
                request.session['authenticator_setup'] = pending
                form = CodeForm()
                form.fields['code'].label = 'Authenticator code'
                form.fields['code'].help_text = 'Enter the current code from your authenticator app.'
        except (service.AccountError, get_user_model().DoesNotExist) as exc:
            error = str(exc) if isinstance(exc, service.AccountError) else 'Account changed. Start setup again.'
        except IntegrityError:
            error = 'An authenticator is already configured. Contact a superuser if it must be replaced.'
            request.session.pop('authenticator_setup', None)
            pending = None
    from .qr import qr_data_uri
    response = render(request, 'accounts/authenticator_setup.html', {
        'form': form, 'secret': pending['secret'] if pending else '', 'error': error, 'notice': notice,
        'qr_image': qr_data_uri(pending['secret'], pending.get('label', 'Personal account')) if pending else '',
    })
    response['Referrer-Policy'] = 'no-referrer'
    return response
