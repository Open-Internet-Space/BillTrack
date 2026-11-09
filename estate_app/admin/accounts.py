from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from rest_framework.authtoken.admin import TokenAdmin as BaseTokenAdmin
from rest_framework.authtoken.models import TokenProxy
from ..models import UserProfile
from ..admin_pagination import PaginationAdminMixin


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(PaginationAdminMixin, BaseUserAdmin):
    change_user_password_template = 'admin/account_user_password_change.html'
    inlines = (UserProfileInline,)
    list_filter = (*BaseUserAdmin.list_filter, 'profile__role')


class GroupAdmin(PaginationAdminMixin, BaseGroupAdmin):
    pass


class TokenAdmin(PaginationAdminMixin, BaseTokenAdmin):
    list_filter = ['user__is_active']
    date_hierarchy = 'created'

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)
admin.site.unregister(TokenProxy)
admin.site.register(TokenProxy, TokenAdmin)
