from django import template

register = template.Library()


@register.simple_tag
def custom_tags(user, perm):
    return user.has_perm(perm)


@register.filter
def has_permission(user, perm):
    print(perm)
    """
    Template filter to check if user has a specific permission.
    Usage: {% if request.user|has_permission:"app_label.permission_code" %}
    """
    return user.has_perm(perm)

