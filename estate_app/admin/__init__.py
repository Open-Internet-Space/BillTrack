"""Public imports retained while implementation lives in focused modules."""
from .common import money, delete_link, ReceiptStatusFilter
from .accounts import UserProfileInline, UserAdmin, GroupAdmin, TokenAdmin
from .settings import SystemSettingsAdmin
from .allottees import TenantAdmin
from .estate import AllotmentAdmin, RequirementAdmin, RentRevisionAdmin
from .charges import EstateChargeAdmin, EstateChargePaymentAdmin
from .security import SecurityMovementAdmin
from .billing import PaymentInline, BillAdminForm, BillAdmin
from .payments import PaymentAdmin

from django.contrib import admin

admin.site.site_header = "BillTrack"
admin.site.site_title = "BillTrack Admin"
admin.site.index_title = "Dashboard"
admin.site.index_template = "admin/estate_app/index.html"
admin.site.password_change_template = 'admin/account_password_change.html'

from ..reminders.admin import ReminderSettingsAdmin, ReminderDeliveryAdmin

from ..email_drafts.admin import EmailTemplateAdmin
from ..activity.admin import ActivityEntryAdmin
