import base64
import binascii

from django import forms
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from . import service
from .qr import qr_data_uri


class EmergencyKeyForm(forms.Form):
    password = forms.CharField(label='Your current superuser password', max_length=256,
                               widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


@never_cache
@require_http_methods(['GET', 'POST'])
def emergency_authenticator(request):
    if not request.user.is_superuser or not service.permitted(request.user):
        return HttpResponseForbidden('Only a superuser can provision emergency recovery.')
    form = EmergencyKeyForm(request.POST if request.method == 'POST' else None)
    secret, image, error = '', '', ''
    if request.method == 'POST':
        try:
            service.limit('emergency-provision', str(request.user.pk), 5, 900)
            if form.is_valid():
                if not request.user.check_password(form.cleaned_data['password']):
                    raise service.AccountError('The current password is incorrect.')
                value = settings.TOTP_RESET_SECRET.strip().upper()
                if not value:
                    raise service.AccountError('The special superuser TOTP is not configured. Set TOTP_RESET_SECRET in the private installation configuration.')
                try:
                    key = base64.b32decode(value + '=' * (-len(value) % 8))
                    if not key:
                        raise ValueError()
                except (binascii.Error, ValueError):
                    raise service.AccountError('The configured emergency key is invalid. Ask the server operator to correct it.') from None
                secret = value
                image = qr_data_uri(secret, 'Superuser emergency (all accounts)')
        except service.AccountError as exc:
            error = str(exc)
    from django.contrib import admin
    response = render(request, 'admin/emergency_authenticator.html', {
        **admin.site.each_context(request), 'title': 'Superuser emergency TOTP',
        'form': form, 'secret': secret, 'qr_image': image, 'error': error,
    })
    response['Referrer-Policy'] = 'no-referrer'
    return response
