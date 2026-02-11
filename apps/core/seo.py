"""
SEO - Sitemap configuration for search engines
Django 사이트맵: 검색 엔진에 크롤링할 페이지 목록을 알려주는 XML 파일 생성
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.coordinates.models import Coordinate
from apps.farming.models import FarmingJournal, FarmingRequest


class StaticSitemap(Sitemap):
    """정적 페이지용 사이트맵 (홈, 안내 등)"""
    priority = 0.8
    changefreq = 'weekly'
    
    def items(self):
        return ['core:landing', 'core:guide', 'coordinates:list', 'coordinates:map', 'farming:home']
    
    def location(self, item):
        return reverse(item)


class CoordinateSitemap(Sitemap):
    """좌표 게시글 사이트맵"""
    changefreq = 'daily'
    priority = 0.6
    
    def items(self):
        # 승인된 좌표만 검색 엔진에 노출
        return Coordinate.objects.filter(status='APPROVED').order_by('-created_at')[:500]
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        return reverse('coordinates:detail', kwargs={'pk': obj.pk})


class FarmingJournalSitemap(Sitemap):
    """농사 일지 사이트맵"""
    changefreq = 'weekly'
    priority = 0.5
    
    def items(self):
        return FarmingJournal.objects.order_by('-created_at')[:200]
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        return reverse('farming:journal_detail', kwargs={'pk': obj.pk})


class FarmingRequestSitemap(Sitemap):
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
