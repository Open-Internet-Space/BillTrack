from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache
from estate_app.models import SystemSettings
from estate_app.views import totp_password_reset
from estate_app.data_transfer import transfer_view, export_view, backup_view

from estate_app.reminders.admin import reminder_view
from estate_app.maintenance import rollback_view, modification_view
from estate_app.account_security.views import account_page, approvals
from estate_app.account_security.totp import authenticator_setup
from estate_app.account_security.emergency import emergency_authenticator

class FrontendView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs),
                'new_signups': SystemSettings.feature_enabled('new_signups_enabled')}


urlpatterns = [
    path('admin/emergency-authenticator/', admin.site.admin_view(emergency_authenticator), name='admin-emergency-authenticator'),
    path('accounts/authenticator/', authenticator_setup, name='account-authenticator'),
    path('accounts/signup/', account_page, {'purpose': 'signup'}, name='account-signup'),
    path('accounts/verify-email/', account_page, {'purpose': 'verify'}, name='account-verify-email'),
    path('accounts/password-reset/', account_page, {'purpose': 'recovery'}, name='account-recovery'),
    path('admin/account-approvals/', admin.site.admin_view(approvals), name='account-approvals'),
    path('admin/rollbacks/', admin.site.admin_view(rollback_view), name='admin-rollbacks'),
    path('admin/modification-guide/', admin.site.admin_view(modification_view), name='admin-modification-guide'),
    path('admin/email-reminders/', admin.site.admin_view(reminder_view), name='admin-email-reminders'),
    path('admin/data-transfer/', admin.site.admin_view(transfer_view), name='admin-data-transfer'),
    path('admin/data-transfer/export/', admin.site.admin_view(export_view), name='admin-data-transfer-export'),
    path('admin/data-transfer/backups/<uuid:backup_id>/', admin.site.admin_view(backup_view), name='admin-data-transfer-backup'),
    path('admin/password-reset/totp/', totp_password_reset, name='totp-password-reset'),
    path('admin/', admin.site.urls),
    path('api/', include('estate_app.urls')),

    # React frontend
    re_path(r'^$', never_cache(FrontendView.as_view())),
]

handler400 = 'estate_app.error_handling.bad_request'
handler403 = 'estate_app.error_handling.permission_denied'
handler404 = 'estate_app.error_handling.page_not_found'
handler500 = 'estate_app.error_handling.server_error'
