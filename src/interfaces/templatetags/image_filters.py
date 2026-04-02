from django import template

register = template.Library()


@register.filter
def stars(value):
    """Return a string of filled star characters for a given integer rating."""
    return "★" * int(value)


@register.filter
def signed(value):
    """Format an integer with an explicit sign: +2, 0, -2."""
    if value is None:
        return "0"
    value = int(value)
    if value > 0:
        return f"+{value}"
    return str(value)
