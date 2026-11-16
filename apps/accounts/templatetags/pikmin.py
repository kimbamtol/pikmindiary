"""피크민 표식 템플릿 태그.

SVG 는 static/js/pikmin.js 한 곳에서만 만든다. 여기서는 그릴 자리와
필요한 값만 내보낸다 — 같은 그림을 두 군데서 그리면 반드시 어긋난다.
"""
from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def pikmin_mark(user):
    """이름 옆에 설 피크민. 글쓴이가 없으면(비회원 글) 아무것도 안 그린다."""
    if not user or not getattr(user, 'pk', None):
        return ''
    mount = user.pikmin_mount_key
    return format_html(
        '<span class="pk-mark{}" data-pk-c="{}" data-pk-f="{}" data-pk-l="{}"'
        ' data-pk-t="{}" data-pk-h="{}" data-pk-s="{}" data-pk-m="{}"></span>',
        ' has-mount' if mount else '',
        user.pikmin_color_key,
        user.pikmin_flower_key,
        user.pikmin_leaf_key,
        user.pikmin_tier,
        user.pikmin_herd,
        user.pikmin_sub_key,
        mount,
    )
