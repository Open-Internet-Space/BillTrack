"""
BillTrack - Django Settings
Local, office LAN and private Tailscale production settings
"""

from pathlib import Path
import ipaddress
import os
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

_debug = os.getenv('DEBUG', 'false').strip().lower()
if _debug not in ('true', 'false', '1', '0'):
    raise ImproperlyConfigured('DEBUG must be true or false.')
DEBUG = _debug in ('true', '1')
SECRET_KEY = os.getenv('SECRET_KEY', '')
if DEBUG and not SECRET_KEY:
    SECRET_KEY = 'dev-only-estate-management-secret-key-change-in-production'
if not DEBUG and (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5
                  or SECRET_KEY.startswith(('dev-only-', 'django-insecure-'))):
    raise ImproperlyConfigured('Set a private SECRET_KEY of at least 50 characters before production startup.')

BILLTRACK_TAILSCALE_IP = os.getenv('BILLTRACK_TAILSCALE_IP', '').strip()
if BILLTRACK_TAILSCALE_IP:
    try:
        if ipaddress.ip_address(BILLTRACK_TAILSCALE_IP) not in ipaddress.ip_network('100.64.0.0/10'):
            raise ValueError
    except ValueError as error:
        raise ImproperlyConfigured('BILLTRACK_TAILSCALE_IP must be a Tailscale IPv4 address.') from error

BILLTRACK_LAN_IP = os.getenv('BILLTRACK_LAN_IP', '').strip()
if BILLTRACK_LAN_IP:
    try:
        _lan = ipaddress.ip_address(BILLTRACK_LAN_IP)
        if not any(_lan in ipaddress.ip_network(network) for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
            raise ValueError
    except ValueError as error:
        raise ImproperlyConfigured('BILLTRACK_LAN_IP must be a private office IPv4 address.') from error

_default_hosts = ['localhost', '127.0.0.1'] + ([BILLTRACK_TAILSCALE_IP] if BILLTRACK_TAILSCALE_IP else []) + ([BILLTRACK_LAN_IP] if BILLTRACK_LAN_IP else [])
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', ','.join(_default_hosts)).split(',') if host.strip()]
if not ALLOWED_HOSTS or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host)
                            or '..' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('ALLOWED_HOSTS must contain exact hostnames or IPv4 addresses; wildcards are not allowed.')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv(
    'CSRF_TRUSTED_ORIGINS', ','.join('http://' + host + ':8000' for host in ALLOWED_HOSTS)).split(',') if origin.strip()]
for _origin in CSRF_TRUSTED_ORIGINS:
    try:
        _parsed = urlsplit(_origin)
        _port = _parsed.port
        if (_parsed.scheme not in ('http', 'https') or _parsed.hostname not in ALLOWED_HOSTS
                or _parsed.username or _parsed.password or _parsed.path or _parsed.query or _parsed.fragment):
            raise ValueError
    except ValueError as error:
        raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS must contain exact origins for allowed hosts, without paths.') from error

# Local/office HTTP and HTTP inside the encrypted tailnet are intentional for this installation.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_HSTS_SECONDS = 0
SECURE_PROXY_SSL_HEADER = None

# ── APPLICATIONS ─────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',

    'estate_app',
]

# ── MIDDLEWARE ──────────────────────────────────────────────
MIDDLEWARE = [
    'estate_app.error_handling.RequestReferenceMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',

    'django.middleware.csrf.CsrfViewMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'estate_app.activity.middleware.ActivityContextMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'estate_project.urls'

# ── TEMPLATES ───────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'frontend_build', BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'estate_project.wsgi.application'

# ── DATABASE ────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {'timeout': 30},
    }
}

# ── PASSWORD VALIDATION ─────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── INTERNATIONALIZATION ────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ── STATIC FILES ────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'frontend_build' / 'static',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── MEDIA FILES ─────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── REST FRAMEWORK ──────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'estate_app.account_security.authentication.AccountTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 200,
}

AUTHENTICATION_BACKENDS = ['estate_app.account_security.authentication.AccountBackend']
ACCOUNT_EMAIL_ENABLED = os.getenv('ACCOUNT_EMAIL_ENABLED', 'false').lower() == 'true'

# ── BUSINESS LOGIC ──────────────────────────────────────────
PENALTY_RATE_PA = 0.12
GST_RATE = 0.18
TOTP_RESET_SECRET = os.getenv('TOTP_RESET_SECRET', '')

# Production diagnostics retain references and stack locations, not credentials or request bodies.
CSRF_FAILURE_VIEW = 'estate_app.error_handling.csrf_failure'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {'safe_errors': {'()': 'estate_app.error_handling.SafeErrorFilter'}},
    'formatters': {'safe_errors': {'()': 'estate_app.error_handling.SafeErrorFormatter',
                                  'format': '%(asctime)s %(levelname)s %(name)s %(message)s'}},
    'handlers': {'safe_console': {'class': 'logging.StreamHandler', 'filters': ['safe_errors'], 'formatter': 'safe_errors'}},
    'loggers': {name: {'handlers': ['safe_console'], 'level': 'WARNING', 'propagate': False}
                for name in ('django', 'django.request', 'django.security', 'django.server')},
}

# Outgoing reminders: private installation credentials, never administrator export data.
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 15
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
