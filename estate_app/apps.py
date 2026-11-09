from django.apps import AppConfig


class EstateAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estate_app'
    verbose_name = 'BillTrack'

    def ready(self):
        from .account_security import signals  # noqa: F401
