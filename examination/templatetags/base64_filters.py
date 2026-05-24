import base64

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def b64encode(value):
    """将字节数据编码为 base64 字符串"""
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("utf-8")
    return value
