"""Core context processors - 새 디자인(수첩) 체험 상태"""
from django.urls import reverse

from .models import SiteSettings, DesignVote

UI_COOKIE = 'pd_ui'
POPUP_COOKIE = 'pd_beta_popup'
UI_NOTEBOOK = 'notebook'


def design_beta(request):
    """새 디자인 체험 상태를 모든 템플릿에 전달"""
    try:
        settings_obj = SiteSettings.get_settings()
        enabled = settings_obj.design_beta_enabled
        popup_enabled = settings_obj.design_beta_popup_enabled
    except Exception:
        # 마이그레이션 전이거나 DB 접근 실패 시 조용히 꺼둔다
        return {'beta_enabled': False, 'ui_notebook': False, 'beta_popup_show': False}

    ui_notebook = enabled and request.COOKIES.get(UI_COOKIE) == UI_NOTEBOOK

    # 팝업: 좌표 목록 첫 진입 시, 아직 체험 중이 아니고, 닫은 적 없을 때
    popup_show = False
    if enabled and popup_enabled and not ui_notebook:
        try:
            on_list = request.path == reverse('coordinates:list')
        except Exception:
            on_list = False
        popup_show = on_list and not request.COOKIES.get(POPUP_COOKIE)

    # 체험 중일 때만 내 투표 상태를 조회한다
    my_vote = ''
    if ui_notebook:
        vote = _find_vote(request)
        my_vote = vote.choice if vote else ''

    return {
        'beta_enabled': enabled,
        'ui_notebook': ui_notebook,
        'beta_popup_show': popup_show,
        'my_design_vote': my_vote,
    }


def _find_vote(request):
    """현재 사용자(회원/비회원)의 투표 찾기"""
    if request.user.is_authenticated:
        return DesignVote.objects.filter(user=request.user).first()
    key = request.session.session_key
    if not key:
        return None
    return DesignVote.objects.filter(user__isnull=True, session_key=key).first()
