"""
SEO - Sitemap configuration for search engines
Django 사이트맵: 검색 엔진에 크롤링할 페이지 목록을 알려주는 XML 파일 생성
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.coordinates.models import Coordinate
from apps.farming.models import FarmingJournal, FarmingRequest


class CanonicalSitemap(Sitemap):
    """주소를 settings.SITE_URL 한 군데에서만 가져오는 사이트맵.

    Django 기본 사이트맵은 django.contrib.sites 의 Site.domain 을 쓴다.
    그러면 정식 주소를 정하는 곳이 두 군데가 된다 - canonical 태그는
    SITE_URL 을 보고, 사이트맵은 DB 의 Site 레코드를 본다. 둘이 엇갈리면
    구글에 서로 다른 주소를 알려주는 셈이라 한쪽으로 모았다.
    """

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc

    def get_protocol(self, protocol=None):
        return urlsplit(settings.SITE_URL).scheme or 'https'


class StaticSitemap(CanonicalSitemap):
    """정적 페이지용 사이트맵 (홈, 안내 등)"""
    priority = 0.8
    changefreq = 'weekly'
    
    def items(self):
        return ['core:landing', 'core:guide', 'coordinates:list', 'coordinates:map', 'farming:home']
    
    def location(self, item):
        return reverse(item)


class CoordinateSitemap(CanonicalSitemap):
    """좌표 게시글 사이트맵"""
    changefreq = 'daily'
    priority = 0.6
    
    def items(self):
        # 승인된 좌표를 전부 넣는다. 예전에는 [:500] 으로 잘라서 최신 500개만
        # 알려줬는데, 글이 쌓이면서 500번째 밖으로 밀려난 2,100여 개를 구글이
        # 다시 확인하러 오지 않았다 (2026-11-27 서치 콘솔에서 발견).
        # 구글 한 파일 한도는 5만 개라 당분간 쪼갤 필요가 없다.
        return Coordinate.objects.filter(status='APPROVED').order_by('-created_at')
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        return reverse('coordinates:detail', kwargs={'pk': obj.pk})


class FarmingJournalSitemap(CanonicalSitemap):
    """농사 일지 사이트맵"""
    changefreq = 'weekly'
    priority = 0.5
    
    def items(self):
        return FarmingJournal.objects.order_by('-created_at')[:200]
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        return reverse('farming:journal_detail', kwargs={'pk': obj.pk})


class FarmingRequestSitemap(CanonicalSitemap):
    """농사 요청 사이트맵"""
    changefreq = 'daily'
    priority = 0.5
    
    def items(self):
        return FarmingRequest.objects.filter(status='open').order_by('-created_at')[:100]
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        return reverse('farming:request_detail', kwargs={'pk': obj.pk})


# 사이트맵 모음 - urls.py에서 사용
sitemaps = {
    'static': StaticSitemap,
    'coordinates': CoordinateSitemap,
    'journals': FarmingJournalSitemap,
    'requests': FarmingRequestSitemap,
}
