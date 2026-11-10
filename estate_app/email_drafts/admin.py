from django.contrib import admin
from ..models import EmailTemplate
from ..admin_pagination import PaginationAdminMixin
from .validation import PLACEHOLDER_DETAILS


@admin.register(EmailTemplate)
class EmailTemplateAdmin(PaginationAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'active')
    list_filter = ('active',)
    search_fields = ('name',)
    change_form_template = 'admin/estate_app/emailtemplate/change_form.html'

    def render_change_form(self, request, context, *args, **kwargs):
        context['email_placeholders'] = PLACEHOLDER_DETAILS
        return super().render_change_form(request, context, *args, **kwargs)

    class Media:
        js = ('estate_app/email_template_placeholders.js',)
        css = {'all': ('estate_app/email_template_placeholders.css',)}
