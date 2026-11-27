"""검색 엔진에 보이는 것들 - 사이트맵과 정식 주소(canonical)

2026-11-27 구글 서치 콘솔에서 두 가지가 드러났다.

1. 사이트맵이 `[:500]` 으로 잘려 있어서, 승인된 글 2,636개 중 2,136개를
   구글이 아예 몰랐다. 색인된 페이지 수가 계속 내려가고 있었다.
2. canonical 태그가 비어 있고 www 주소도 그대로 열려서, 같은 글이 두 주소에
   있는 것처럼 보였다. 「표준이 없는 중복 페이지」 304건.

여기 있는 테스트는 그 둘이 되돌아오는 것을 막는다.
"""
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.coordinates.models import Coordinate

from .base import BaseTest


class SitemapTest(BaseTest):
    """사이트맵에 글이 빠지지 않는가"""

    def _locs(self):
        r = self.client.get('/sitemap.xml')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        import re
        return re.findall(r'<loc>([^<]+)</loc>', body)

    def test_승인된_글이_전부_들어간다(self):
        """개수를 센다. 이게 `[:500]` 같은 자르기를 막는 핵심이다 -
        글이 몇 개든 사이트맵에 그만큼 들어 있어야 한다."""
        for i in range(12):
            self.make_coord(title='글%d' % i)

        locs = self._locs()
        for c in Coordinate.objects.filter(status=Coordinate.Status.APPROVED):
            self.assertIn('/coordinates/%d/' % c.pk, ' '.join(locs),
                          '#%d 이 사이트맵에 없다' % c.pk)

    def test_개수가_글_수를_따라간다(self):
        """글을 더 넣으면 사이트맵도 그만큼 늘어나야 한다.
        어딘가에서 잘리면 늘어나지 않으므로 바로 잡힌다."""
        for i in range(5):
            self.make_coord(title='처음%d' % i)
        before = len(self._locs())

        for i in range(7):
            self.make_coord(title='나중%d' % i)
        after = len(self._locs())

        self.assertEqual(after - before, 7)

    def test_승인_안_된_글은_안_들어간다(self):
        mine = self.make_coord(title='대기중', status=Coordinate.Status.PENDING)
        self.assertNotIn('/coordinates/%d/' % mine.pk, ' '.join(self._locs()))

    def test_주소는_전부_정식_주소다(self):
        """www 나 http 로 적히면 구글이 중복으로 센다."""
        self.make_coord()
        for loc in self._locs():
            self.assertTrue(loc.startswith(settings.SITE_URL.rstrip('/') + '/'),
                            '정식 주소가 아니다: %s' % loc)

    def test_글이_늘어도_쿼리가_늘지_않는다(self):
        """사이트맵은 승인된 글을 전부 훑는다. 글마다 한 번씩 물어보면
        2,600개에서 그대로 터진다."""
        def count():
            self.client.get('/sitemap.xml')          # 예열
            with CaptureQueriesContext(connection) as ctx:
                self.client.get('/sitemap.xml')
            return len(ctx.captured_queries)

        for i in range(5):
            self.make_coord(title='소%d' % i)
        few = count()

        for i in range(35):
            self.make_coord(title='대%d' % i)
        many = count()

        self.assertEqual(few, many,
                         '글 5개에서 %d개, 40개에서 %d개. 글마다 묻고 있다.'
                         % (few, many))


class CanonicalTest(BaseTest):
    """정식 주소를 제대로 못박는가"""

    def _canonical(self, url, **extra):
        import re
        r = self.client.get(url, **extra)
        self.assertEqual(r.status_code, 200, url)
        m = re.search(r'<link rel="canonical" href="([^"]+)"', r.content.decode())
        self.assertIsNotNone(m, '%s 에 canonical 태그가 없다' % url)
        return m.group(1).replace('&amp;', '&')

    def test_주요_화면에_canonical이_있다(self):
        coord = self.make_coord()
        base = settings.SITE_URL.rstrip('/')
        for url, want in (
            ('/', base + '/'),
            ('/coordinates/', base + '/coordinates/'),
            ('/coordinates/%d/' % coord.pk, base + '/coordinates/%d/' % coord.pk),
        ):
            self.assertEqual(self._canonical(url), want)

    def test_www로_들어와도_정식_주소를_말한다(self):
        """이게 중복 304건의 해법이다. nginx 가 301로 넘기지만, 예전에
        www 로 퍼진 링크가 남아 있으니 페이지 자체도 같은 말을 해야 한다."""
        self.make_coord()
        got = self._canonical('/coordinates/', HTTP_HOST='www.pikmindiary.com')
        self.assertEqual(got, settings.SITE_URL.rstrip('/') + '/coordinates/')
        self.assertNotIn('www.', got)

    def test_쪽수는_절대_떼지_않는다(self):
        """2쪽 이후 글로 구글이 찾아가는 길은 이것뿐이다. 쪽수 페이지의
        canonical 을 1쪽으로 보내면 그 글들이 색인에서 사라진다."""
        for i in range(60):
            self.make_coord(title='글%d' % i)
        self.assertIn('page=3', self._canonical('/coordinates/?page=3'))

    def test_쪽수_1은_뗀다(self):
        """1쪽은 쿼리 없는 주소와 같은 화면이다."""
        self.make_coord()
        self.assertEqual(self._canonical('/coordinates/?page=1'),
                         settings.SITE_URL.rstrip('/') + '/coordinates/')

    def test_분류와_지역은_남는다(self):
        self.make_coord()
        got = self._canonical('/coordinates/?category=MUSHROOM&region=KR')
        self.assertIn('category=MUSHROOM', got)
        self.assertIn('region=KR', got)

    def test_정렬과_검색어는_뗀다(self):
        """정렬은 같은 글을 순서만 바꾼 것이고, 검색 결과는 색인될 이유가 없다."""
        self.make_coord()
        got = self._canonical('/coordinates/?sort=popular&q=%EB%B2%84%EC%84%AC')
        self.assertNotIn('sort=', got)
        self.assertNotIn('q=', got)

    def test_og_url도_같은_주소를_쓴다(self):
        """예전에는 og:url 이 request.get_host 를 썼다. www 로 들어오면
        canonical 과 서로 다른 말을 했다."""
        import re
        r = self.client.get('/coordinates/', HTTP_HOST='www.pikmindiary.com')
        body = r.content.decode()
        og = re.search(r'<meta property="og:url" content="([^"]+)"', body).group(1)
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', body).group(1)
        self.assertEqual(og, canon)
        self.assertNotIn('www.', og)
