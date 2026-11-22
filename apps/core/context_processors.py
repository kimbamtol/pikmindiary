"""Core context processors - 디자인 선택(수첩/기존) 상태와 목록 보기 밀도"""
from .models import SiteSettings

UI_COOKIE = 'pd_ui'
UI_NOTEBOOK = 'notebook'
UI_CLASSIC = 'classic'
DENSITY_COOKIE = 'pd_density'
DENSITIES = ('large', 'normal', 'dense')

PAGING_COOKIE = 'pd_paging'
PAGINGS = ('pages', 'scroll')

# 화면 폭은 서버가 알 수 없다. 브라우저가 접속할 때 쿠키에 'pc'/'mo' 를 적어준다.
# 쿠키가 없으면(첫 방문, 검색엔진) 좁은 쪽으로 친다 - 넘치는 것보다 모자란 게 낫다.
WIDTH_COOKIE = 'pd_w'
PAGE_SIZE_PC = 30      # 2열 15줄 / 3열 10줄 / 5열 6줄 - 어느 밀도에서도 줄이 딱 떨어진다
PAGE_SIZE_NARROW = 24  # 1열 24줄 / 2열 12줄 / 3열 8줄 / 4열 6줄


def paging_mode(request):
    """목록 넘기기 방식 한 글자. 회원은 계정, 비회원은 쿠키, 둘 다 없으면 쪽수"""
    value = ''
    if request.user.is_authenticated:
        value = getattr(request.user, 'list_paging', '') or ''
    if value not in PAGINGS:
        value = request.COOKIES.get(PAGING_COOKIE, '')
    if value not in PAGINGS:
        value = 'pages'
    return value


def page_size(request):
    """한 쪽에 몇 장을 보낼지. 화면 폭 쿠키를 본다"""
    if request.COOKIES.get(WIDTH_COOKIE) == 'pc':
        return PAGE_SIZE_PC
    return PAGE_SIZE_NARROW


def list_paging(request):
    """목록 넘기기 방식을 모든 템플릿에 전달"""
    return {'list_paging': paging_mode(request)}


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
