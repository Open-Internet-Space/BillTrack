from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from ..models import AccountAccess, EmailChallenge


@receiver(post_save, sender=get_user_model())
def invalidate_changed_email(sender, instance, **kwargs):
    AccountAccess.objects.filter(user=instance, signup_email__isnull=False).exclude(
        signup_email=instance.email.strip().casefold()).update(signup_email=None)
    rows = AccountAccess.objects.filter(user=instance, verified_email__isnull=False)
    if rows.exclude(verified_email=instance.email.strip().casefold()).update(verified_email=None, verified_at=None):
        EmailChallenge.objects.filter(user=instance, consumed=False).update(consumed=True)
