from django.contrib import admin
from ..models import EmailTemplate
from ..admin_pagination import PaginationAdminMixin

@admin.register(EmailTemplate)
class EmailTemplateAdmin(PaginationAdminMixin,admin.ModelAdmin):
    list_display=('name','active')
    list_filter=('active',)
    search_fields=('name',)
