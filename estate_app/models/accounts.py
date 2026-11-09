from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [('admin', 'Admin'), ('staff', 'Staff')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='staff')

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class PasswordResetAttempt(models.Model):
    account_key = models.CharField(max_length=64, primary_key=True)
    window_started = models.BigIntegerField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
