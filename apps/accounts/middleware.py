"""사용자/IP 차단 + IP 기반 언어 감지 미들웨어"""
import logging
import urllib.request
import json

from django.conf import settings
from django.http import HttpResponseForbidden
from django.template.loader import render_to_string
from django.utils import translation

from .models import UserBan

logger = logging.getLogger(__name__)

# 국가 코드 → 언어 매핑
COUNTRY_LANGUAGE_MAP = {
    'KR': 'ko',
    'JP': 'ja',
}


class IPLanguageMiddleware:
    """
    첫 방문 시 IP로 국가를 판별하여 언어를 자동 설정하는 미들웨어.
    - django_language 쿠키가 없을 때만 동작 (수동 선택 우선)
    - 세션에 결과를 캐시하여 API 호출 최소화
    - LocaleMiddleware 앞에 배치
    """

    SKIP_PATHS = ['/static/', '/media/', '/i18n/', '/admin/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 정적 파일, 언어 변경 요청 등은 스킵
        if any(request.path.startswith(p) for p in self.SKIP_PATHS):
            return self.get_response(request)

        # 이미 사용자가 수동으로 언어를 선택했으면 스킵
        if request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            return self.get_response(request)

        # 세션에 이미 감지된 언어가 있으면 사용
        detected_lang = request.session.get('ip_detected_lang')

        if not detected_lang:
            # IP로 국가 판별
            ip = self._get_client_ip(request)
            if ip:
                country = self._get_country_from_ip(ip)
                detected_lang = COUNTRY_LANGUAGE_MAP.get(country, 'en')
                request.session['ip_detected_lang'] = detected_lang

        if detected_lang:
            # Django의 언어 활성화
            translation.activate(detected_lang)
            request.LANGUAGE_CODE = detected_lang

        response = self.get_response(request)

        # 응답에 언어 쿠키 설정 (다음 요청부터 LocaleMiddleware가 처리)
        if detected_lang and not request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                detected_lang,
                max_age=365 * 24 * 60 * 60,
                path='/',
                samesite='Lax',
            )

        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _get_country_from_ip(self, ip):
        """ipapi.co API로 국가 코드 조회 (무료, 30k/월)"""
        # 로컬 IP는 한국으로 간주
        if ip in ('127.0.0.1', '::1', 'localhost') or ip.startswith('192.168.') or ip.startswith('10.'):
            return 'KR'

        try:
            url = f'https://ipapi.co/{ip}/country/'
            req = urllib.request.Request(url, headers={'User-Agent': 'PikminDiary/1.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                country = resp.read().decode('utf-8').strip()
                if len(country) == 2 and country.isalpha():
                    return country.upper()
        except Exception as e:
            logger.warning(f'IP geolocation failed for {ip}: {e}')

        return None


class BanCheckMiddleware:
    """요청마다 사용자/IP 차단 여부를 확인하는 미들웨어"""

    # 차단되어도 접근 가능한 경로 (로그아웃 등)
    EXEMPT_PATHS = ['/accounts/logout/', '/static/', '/media/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 정적 파일 등은 스킵
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        # IP 차단 확인
        ip = self._get_client_ip(request)
        if ip and UserBan.is_ip_banned(ip):
            return HttpResponseForbidden(
                '<h1>접근이 제한되었습니다</h1>'
                '<p>이용이 정지된 상태입니다. 문의사항은 관리자에게 연락해주세요.</p>'
            )

        # 로그인 사용자 차단 확인
        if request.user.is_authenticated and UserBan.is_user_banned(request.user):
            return HttpResponseForbidden(
                '<h1>접근이 제한되었습니다</h1>'
                '<p>이용이 정지된 상태입니다. 문의사항은 관리자에게 연락해주세요.</p>'
            )

        return self.get_response(request)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
