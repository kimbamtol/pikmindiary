"""사용자/IP 차단 미들웨어"""
from django.http import HttpResponseForbidden
from django.template.loader import render_to_string

from .models import UserBan


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
