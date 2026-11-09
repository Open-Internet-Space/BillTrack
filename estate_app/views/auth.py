import hashlib
import time

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db.models import F
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ..serializers import UserSerializer
from ..models import PasswordResetAttempt


def _valid_totp(secret, code):
    from ..account_security.totp import matching_counter
    return matching_counter(secret, code) is not None


def _recovery_retry_after(username, now):
    key = hashlib.sha256(username.casefold().encode('utf-8')).hexdigest()
    PasswordResetAttempt.objects.filter(window_started__lt=now - 86400).delete()
    PasswordResetAttempt.objects.get_or_create(account_key=key, defaults={'window_started': now})
    account = PasswordResetAttempt.objects.filter(account_key=key)
    account.filter(window_started__lte=now - 900).update(window_started=now, attempts=0)
    # Conditional database increments share the budget across concurrent clients and processes.
    if account.filter(attempts__lt=5).update(attempts=F('attempts') + 1):
        return 0
    return max(1, account.get().window_started + 900 - now)


@never_cache
@require_http_methods(['GET', 'POST'])
def totp_password_reset(request):
    error = ''
    retry_after = 0
    if request.method == 'POST':
        now = int(time.time())
        username = get_user_model().normalize_username(request.POST.get('username', '').strip())
        from ..account_security.service import find_user, AccountError, RateLimitError
        from ..account_security.totp import reset_password
        user = find_user(username) if len(username) <= 254 else None
        retry_after = _recovery_retry_after(user.username if user else username, now)
        if retry_after:
            error = f'Too many recovery attempts. Try again in {(retry_after + 59) // 60} minute(s).'
        else:
            password = request.POST.get('password', '')
            confirmation = request.POST.get('password_confirm', '')
            try:
                succeeded = reset_password(user, request.POST.get('code', ''), password, confirmation, _valid_totp,
                                           emergency=request.POST.get('recovery_method') == 'emergency')
                if succeeded:
                    if user.is_staff:
                        messages.success(request, 'Password updated. You can now sign in.')
                        return redirect('admin:login')
                    return render(request, 'admin/totp_password_reset.html', {'success': True, 'available': True})
                error = 'The username or authenticator code is invalid.'
            except ValidationError as exc:
                error = 'Passwords do not match.' if getattr(exc, 'code', '') == 'mismatch' else 'Choose a stronger password.'
            except RateLimitError as exc:
                retry_after = exc.retry_after
                error = f'Too many emergency recovery attempts. Try again in {(retry_after + 59) // 60} minute(s).'
            except AccountError:
                error = 'The username or authenticator code is invalid.'
    response = render(request, 'admin/totp_password_reset.html', {'error': error, 'available': True}, status=429 if retry_after else 200)
    if retry_after:
        response['Retry-After'] = str(retry_after)
    return response
# ══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    if not hasattr(request.data, 'get'):
        return Response({'error': 'Invalid credentials'}, status=401)
    username = request.data.get('username')
    password = request.data.get('password')

    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 254 or len(password) > 256:
        return Response({'error': 'Invalid credentials'}, status=401)

    user = authenticate(username=username, password=password)

    if not user:
        candidate = get_user_model().objects.filter(username=username).first() if isinstance(username, str) else None
        if not candidate and isinstance(username, str):
            from ..account_security.service import email_owner
            candidate = email_owner(username.strip().casefold())
        if candidate and candidate.check_password(password or ''):
            from ..models import AccountAccess
            access = AccountAccess.objects.filter(user=candidate).first()
            if access and access.status != 'approved':
                state = ('Awaiting superuser approval.' if access.verified_at else 'Verify your signup email before approval.') if access.status == 'pending' else 'Your account application was rejected. Contact a superuser.'
                return Response({'error': state}, status=403)
        return Response({'error': 'Invalid credentials'}, status=401)

    if not user.is_active:
        return Response({'error': 'Account disabled'}, status=403)

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    request.user.auth_token.delete()
    return Response({'message': 'Logged out successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserSerializer(request.user).data)
