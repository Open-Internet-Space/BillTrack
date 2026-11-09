from django import template

register = template.Library()


@register.filter
def report_value(row, key):
    return row.get(key, '')
