"""자랑 게시판 위젯용 템플릿 태그"""
from django import template

from apps.brag.models import BragPost

register = template.Library()


@register.inclusion_tag('brag/_widget_top.html')
def weekly_top_brag():
    """주간 1위 (좌표 목록 사이드바용). 이번 주가 비면 지난주 우승자"""
    return BragPost.current_top()
