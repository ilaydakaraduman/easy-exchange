from django import template

register = template.Library()


@register.filter
def has_key(mapping, key):
    return isinstance(mapping, dict) and key in mapping


@register.filter
def dict_get(mapping, key):
    if not isinstance(mapping, dict):
        return ""
    return mapping.get(key, "")
