"""피크민 표식 템플릿 태그.

SVG 는 static/js/pikmin.js 한 곳에서만 만든다. 여기서는 그릴 자리와
필요한 값만 내보낸다 — 같은 그림을 두 군데서 그리면 반드시 어긋난다.
"""
from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def pikmin_mark(user, force=False):
    """이름 옆에 설 피크민.

    **본인이 켠 사람만 보인다.** 끈 사람에게도 자리는 내보내되 감춰둔다 —
    복사 효과가 이 값을 읽어 무리를 만들기 때문이다. 복사 효과는 끄는 것이
    아니라서 표식을 껐다고 값까지 없애면 무리가 안 나간다.

    force=True 는 설정 화면 미리보기용이다. 거기서는 꺼놔도 보여야 한다.
    """
    if not user or not getattr(user, 'pk', None):
        return ''
    mount = user.pikmin_mount_key
    show = force or user.pikmin_show_mark
    return format_html(
        '<span class="pk-mark{}{}" data-pk-show="{}" data-pk-c="{}" data-pk-f="{}"'
        ' data-pk-l="{}" data-pk-t="{}" data-pk-h="{}" data-pk-s="{}" data-pk-m="{}"></span>',
        ' has-mount' if (show and mount) else '',
        '' if show else ' pk-hidden',
        '1' if show else '0',
        user.pikmin_color_key,
        user.pikmin_flower_key,
        user.pikmin_leaf_key,
        user.pikmin_tier,
        user.pikmin_herd,
        user.pikmin_sub_key,
        mount,
    )
