"""Core views - 랜딩 페이지 및 안내 페이지"""
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone

from .models import Suggestion


def landing_page(request):
    """랜딩 페이지 - 서버 위치 기준 계절/날씨 UI"""
    from apps.rankings.models import Ranking

    month_start = timezone.now().date().replace(day=1)
    top_contributors = Ranking.objects.filter(
        period_type=Ranking.PeriodType.MONTHLY,
        period_start=month_start,
        approved_posts_count__gt=0
    ).select_related('user').order_by('rank')[:3]

    context = {
        'default_location': settings.DEFAULT_LOCATION,
        'top_contributors': top_contributors,
        'current_month': month_start,
    }
    return render(request, 'core/landing.html', context)


def guide_page(request):
    """사이트 안내 페이지"""
    return render(request, 'core/guide.html')


def mypage_guide(request):
    """마이페이지 시스템 안내 페이지"""
    return render(request, 'core/mypage_guide.html')


def default_location(request):
    """기본 위치 API (서버 위치 반환)"""
    return JsonResponse({
        'latitude': settings.DEFAULT_LOCATION['latitude'],
        'longitude': settings.DEFAULT_LOCATION['longitude'],
    })


@require_http_methods(["GET", "POST"])
def suggestion_form(request):
    """운영자에게 건의하기 폼"""
    if request.method == 'POST':
        category = request.POST.get('category', 'OTHER')
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        
        if not title or not content:
            messages.error(request, _('제목과 내용을 입력해주세요.'))
            return render(request, 'core/suggestion_form.html', {
                'categories': Suggestion.Category.choices,
            })
        
        suggestion_data = {
            'category': category,
            'title': title,
            'content': content,
        }
        
        if request.user.is_authenticated:
            suggestion_data['author'] = request.user
        else:
            guest_nickname = request.POST.get('guest_nickname', '익명').strip()
            email = request.POST.get('email', '').strip()
            suggestion_data['guest_nickname'] = guest_nickname or '익명'
            suggestion_data['email'] = email
        
        suggestion = Suggestion.objects.create(**suggestion_data)

        # 운영자에게 메일 알림
        try:
            from django.core.mail import mail_admins
            writer = suggestion.writer_name
            mail_admins(
                f'[건의] {suggestion.get_category_display()} - {title}',
                f'작성자: {writer}\n카테고리: {suggestion.get_category_display()}\n\n{content}',
            )
        except Exception:
            pass

        messages.success(request, _('건의사항이 성공적으로 접수되었습니다!'))
        return redirect('core:suggestion_done')
    
    return render(request, 'core/suggestion_form.html', {
        'categories': Suggestion.Category.choices,
    })


def suggestion_done(request):
    """건의 완료 페이지"""
    return render(request, 'core/suggestion_done.html')

# ===== 새 디자인(수첩) 체험 =====

UI_COOKIE = 'pd_ui'
POPUP_COOKIE = 'pd_beta_popup'
UI_NOTEBOOK = 'notebook'
COOKIE_MAX_AGE = 60 * 60 * 24 * 180      # 체험 설정 180일 유지
POPUP_HIDE_MAX_AGE = 60 * 60 * 24 * 7    # 일주일간 보지 않기


def _safe_next(request, default_name='coordinates:list'):
    """열린 리다이렉트 방지: 같은 사이트 경로만 허용"""
    from django.urls import reverse
    from django.utils.http import url_has_allowed_host_and_scheme

    nxt = request.GET.get('next') or request.POST.get('next') or ''
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return reverse(default_name)


def _beta_enabled():
    from .models import SiteSettings
    try:
        return SiteSettings.get_settings().design_beta_enabled
    except Exception:
        return False


def design_beta_on(request):
    """새 디자인으로 전환"""
    response = redirect(_safe_next(request))
    if _beta_enabled():
        response.set_cookie(
            UI_COOKIE, UI_NOTEBOOK, max_age=COOKIE_MAX_AGE,
            samesite='Lax', secure=request.is_secure()
        )
        # 체험을 시작했으면 안내 팝업은 더 띄우지 않는다
        response.set_cookie(
            POPUP_COOKIE, '1', max_age=COOKIE_MAX_AGE,
            samesite='Lax', secure=request.is_secure()
        )
    return response


def design_beta_off(request):
    """기존 디자인으로 복귀"""
    response = redirect(_safe_next(request))
    response.delete_cookie(UI_COOKIE)
    return response


@require_POST
def design_popup_dismiss(request):
    """안내 팝업 닫기. days=7이면 일주일간 보지 않기"""
    days = request.POST.get('days', '')
    response = JsonResponse({'ok': True})
    if days == '7':
        response.set_cookie(
            POPUP_COOKIE, '1', max_age=POPUP_HIDE_MAX_AGE,
            samesite='Lax', secure=request.is_secure()
        )
    else:
        # 이번 방문 동안만 숨김 (브라우저 종료 시 사라짐)
        response.set_cookie(
            POPUP_COOKIE, '1', samesite='Lax', secure=request.is_secure()
        )
    return response


@require_POST
def design_vote(request):
    """디자인 투표 - 비회원 포함 1인 1표, 변경 가능"""
    from .models import DesignVote

    choice = request.POST.get('choice', '')
    if choice not in (DesignVote.Choice.NEW, DesignVote.Choice.OLD):
        return JsonResponse({'ok': False, 'error': '잘못된 선택입니다.'}, status=400)

    comment = (request.POST.get('comment') or '').strip()[:200]
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR')

    if request.user.is_authenticated:
        DesignVote.objects.update_or_create(
            user=request.user,
            defaults={'choice': choice, 'comment': comment, 'ip_address': ip},
        )
    else:
        if not request.session.session_key:
            request.session.save()
        DesignVote.objects.update_or_create(
            user=None, session_key=request.session.session_key,
            defaults={'choice': choice, 'comment': comment, 'ip_address': ip},
        )

    tally = DesignVote.tally()
    return JsonResponse({'ok': True, 'choice': choice, 'tally': tally})
