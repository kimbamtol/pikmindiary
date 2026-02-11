"""
URL configuration for pikmin-diary project.
"""
import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from apps.core.seo import sitemaps

# 관리자 URL은 환경변수에서 읽어옴 (보안)
ADMIN_URL = os.getenv('ADMIN_URL', 'secret-manage-8x7k2m')
DJANGO_ADMIN_URL = os.getenv('DJANGO_ADMIN_URL', 'django-admin-9f3j1p')

urlpatterns = [
    # Django Admin (기본 관리자)
    path(f'{DJANGO_ADMIN_URL}/', admin.site.urls),
    
    # 랜딩 페이지 및 코어 기능
    path('', include('apps.core.urls')),
    
    # 인증 (django-allauth)
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('apps.accounts.urls')),
    
    # 좌표 게시글
    path('coordinates/', include('apps.coordinates.urls')),
    
    # 댓글
    path('comments/', include('apps.comments.urls')),
    
    # 상호작용 (좋아요, 북마크, 유효성 평가)
    path('interactions/', include('apps.interactions.urls')),
    
    # 신고
    path('reports/', include('apps.reports.urls')),
    
    # 랭킹
    path('rankings/', include('apps.rankings.urls')),
    
    # 농사 게시판
    path('farming/', include('apps.farming.urls')),
    
    # 관리자 대시보드
    path(f'{ADMIN_URL}/', include('apps.admin_panel.urls')),
    
    # SEO - 사이트맵 & robots.txt
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt',
        content_type='text/plain'
    )),
]

# 개발 환경에서 미디어 파일 서빙
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
