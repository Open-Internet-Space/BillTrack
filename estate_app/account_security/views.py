import uuid

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from ..models import AccountAccess
from . import service
from .forms import CodeForm, EmailForm, ExistingEmailForm, ResetForm, SignupForm

TITLES = {'signup': 'Create your account', 'verify': 'Verify your account email', 'recovery': 'Reset your password'}
FORMS = {'signup': SignupForm, 'verify': ExistingEmailForm, 'recovery': EmailForm}
GENERIC = 'If the details are eligible, an email code has been submitted. Check your inbox and spam folder.'


def begin(request, purpose, data):
    User = get_user_model()
    if purpose == 'verify':
        service.limit('existing-password', data['username'].strip().casefold(), 5, 900)
        user = authenticate(request, username=data['username'], password=data['password'])
        email = service.canonical_email(user.email) if user and user.email else None
        if not email or service.email_owner(email) != user:
            raise service.AccountError('The account details are invalid, or the saved email needs correction by a superuser.')
        service.send_budget(email, request.META.get('REMOTE_ADDR', 'unknown'))
    else:
        email = data['email']
        service.send_budget(email, request.META.get('REMOTE_ADDR', 'unknown'))
        user = service.email_owner(email)
        if purpose == 'signup':
            if not User.objects.filter(email__iexact=email).exists() and not User.objects.filter(username__iexact=email).exists() and not AccountAccess.objects.filter(verified_email=email).exists():
                with transaction.atomic():
                    user = User.objects.create_user('signup_' + uuid.uuid4().hex, email, data['password'], first_name=data['name'], is_active=False)
                    AccountAccess.objects.create(user=user, status='pending', signup_email=email, signup_created=True)
            elif not (user and user.check_password(data['password']) and not user.is_active
                      and AccountAccess.objects.filter(user=user, status='pending', verified_email__isnull=True).exists()):
                user = None
        elif not (user and service.permitted(user) and AccountAccess.objects.filter(user=user, verified_email=email, verified_at__isnull=False).exists()):
            user = None
    return service.issue(purpose, email, user)


@never_cache
@require_http_methods(['GET', 'POST'])
def account_page(request, purpose):
    enabled = service.available()
    session_key = 'email_challenge_' + purpose
    if request.method == 'GET' and request.GET.get('restart') == '1':
        request.session.pop(session_key, None)
    verifying = request.POST.get('action') == 'verify' if request.method == 'POST' else bool(request.session.get(session_key))
    form_class = (ResetForm if purpose == 'recovery' else CodeForm) if verifying else FORMS[purpose]
    form = form_class(request.POST if request.method == 'POST' and enabled else None)
    error = ''
    notice = ''
    done = False
    if request.method == 'POST' and enabled:
        try:
            service.limit('form-ip', request.META.get('REMOTE_ADDR', 'unknown'), 60, 900)
            if verifying:
                # Charge before the transaction, so rejected guesses cannot roll back their budget.
                service.verification_budget(request.session.get(session_key), purpose)
            if form.is_valid():
                if verifying:
                    service.consume(request.session.get(session_key), purpose, form.cleaned_data['code'], form.cleaned_data.get('password'))
                    notice = ('Password updated. Sign in with your new password.' if purpose == 'recovery' else
                              'Awaiting superuser approval. Your email has been verified.' if purpose == 'signup' else
                              'Your account email is verified. Email password recovery is now available.')
                    request.session.pop(session_key, None)
                    done = True
                else:
                    try:
                        nonce = begin(request, purpose, form.cleaned_data)
                    except service.AccountError as exc:
                        if purpose != 'recovery' or 'could not be submitted' not in str(exc):
                            raise
                        nonce = str(uuid.uuid4())
                    request.session[session_key] = nonce
                    notice = GENERIC
                    verifying = True
                    form = ResetForm() if purpose == 'recovery' else CodeForm()
        except (service.AccountError, ValidationError) as exc:
            error = ' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        except IntegrityError:
            error = 'These account details cannot be used. Contact a superuser if you already have an account.'
    response = render(request, 'accounts/page.html', {
        'title': TITLES[purpose], 'purpose': purpose, 'available': enabled,
        'form': form, 'verifying': verifying, 'error': error, 'notice': notice, 'done': done,
    })
    response['Referrer-Policy'] = 'no-referrer'
    return response


@require_http_methods(['GET', 'POST'])
def approvals(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Only a superuser can manage account approvals.')
    if request.method == 'POST':
        try:
            from ..activity.admin import ReasonForm, apply_reason
            reason_form = ReasonForm(request.POST)
            if not reason_form.is_valid():
                raise service.AccountError('Enter a written reason for this account decision.')
            apply_reason(reason_form.cleaned_data['change_reason'])
            service.decide(int(request.POST.get('account', '')), request.user, request.POST.get('decision'))
            messages.success(request, 'Account decision saved.')
        except (service.AccountError, AccountAccess.DoesNotExist, ValueError) as exc:
            messages.error(request, str(exc) if isinstance(exc, service.AccountError) else 'The account could not be found.')
        return redirect('account-approvals')
    from django.contrib import admin
    from django.core.paginator import Paginator
    page = Paginator(AccountAccess.objects.filter(Q(verified_at__isnull=False) | ~Q(status='pending')).select_related('user', 'decided_by').order_by('-user__date_joined'), 50).get_page(request.GET.get('page'))
    return render(request, 'admin/account_approvals.html', {**admin.site.each_context(request), 'title': 'Account approvals', 'page': page})
