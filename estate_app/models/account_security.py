import uuid

from django.conf import settings
from django.db import models


class AccountAccess(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_access')
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='approved')
    verified_email = models.EmailField(max_length=254, null=True, blank=True, unique=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    signup_email = models.EmailField(max_length=254, null=True, blank=True, unique=True, editable=False)
    signup_created = models.BooleanField(default=False, editable=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)


class EmailChallenge(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    nonce = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=12)
    email = models.EmailField(max_length=254)
    digest = models.CharField(max_length=64)
    password_stamp = models.CharField(max_length=64)
    expires_at = models.BigIntegerField(db_index=True)
    consumed = models.BooleanField(default=False)


class AccountRateLimit(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started = models.BigIntegerField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)


class AccountAuthenticator(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recovery_authenticator')
    # TOTP needs a recoverable seed; database files and backups must stay private.
    secret = models.CharField(max_length=64, editable=False)
    last_counter = models.BigIntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)


class EmergencyRecoveryState(models.Model):
    last_counter = models.BigIntegerField(default=-1)
