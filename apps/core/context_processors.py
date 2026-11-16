"""Core context processors - 디자인 선택(수첩/기존) 상태와 목록 보기 밀도"""
from .models import SiteSettings

UI_COOKIE = 'pd_ui'
UI_NOTEBOOK = 'notebook'
UI_CLASSIC = 'classic'
DENSITY_COOKIE = 'pd_density'
DENSITIES = ('large', 'normal', 'dense')


def list_density(request):
    """목록 보기 밀도. 회원은 계정 설정, 비회원은 쿠키"""
    value = ''
    if request.user.is_authenticated:
        value = getattr(request.user, 'list_density', '') or ''
    if value not in DENSITIES:
        value = request.COOKIES.get(DENSITY_COOKIE, '')
    if value not in DENSITIES:
        value = 'normal'
    return {'list_density': value}


def design_beta(request):
    """디자인 선택 상태를 모든 템플릿에 전달.

    기본값은 수첩 디자인이고, 쿠키에 classic이 들어 있을 때만 기존 디자인을 쓴다.
    사이트 설정에서 꺼두면 전부 기존 디자인으로 돌아간다.
    """
    try:
        enabled = SiteSettings.get_settings().design_beta_enabled
    except Exception:
        # 마이그레이션 전이거나 DB 접근 실패 시 조용히 기존 디자인으로
        return {'beta_enabled': False, 'ui_notebook': False}

    return {
        'beta_enabled': enabled,
        'ui_notebook': enabled and request.COOKIES.get(UI_COOKIE) != UI_CLASSIC,
    }
