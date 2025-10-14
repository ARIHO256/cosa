from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Divide value by arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """Calculate percentage of value out of total"""
    try:
        if float(total) == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def split_string(value, delimiter=','):
    """Split a string by delimiter and return a list"""
    try:
        if not value:
            return []
        return [item.strip() for item in str(value).split(delimiter) if item.strip()]
    except (ValueError, TypeError):
        return []