from django import template

from ..models import SystemSettings

register = template.Library()


@register.simple_tag
def new_signups_enabled():
    return SystemSettings.feature_enabled('new_signups_enabled')
