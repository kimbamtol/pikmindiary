"""지도로 보기 — 무게와 지연율

2026-11-17 에 이 화면이 제일 느렸다. 재보니 이랬다.

  DB 쿼리     2,526개   (좌표마다 사진을 따로 물어봤다 - N+1)
  서버 처리    1,260ms
  HTML          790KB   (gzip 144KB)
  브라우저가 받는 사진   약 280MB  ← 범인
  DOM 노드     20,641개

사진 280MB 의 원인은 사이드바 목록이었다. 화면에 보이는 마커를 **전부** 그렸는데
세계 지도에서는 그게 2,523개이고, `<img>` 에 loading="lazy" 가 없어서
사이트의 모든 사진을 즉시 내려받았다. 지도를 움직일 때마다 처음부터 다시 그렸다.

여기서 지키는 것:
  1. 쿼리 수가 **글 수에 따라 늘지 않는다** (N+1 재발 방지 - 이게 핵심이다)
  2. 글마다 반복되는 문자열을 JSON 에 넣지 않는다 (이름표는 한 번만)
  3. 화면 쪽 안전장치가 템플릿에 실제로 들어 있다
     (목록 상한 / loading="lazy" / debounce / chunkedLoading)
"""
import json
import re
import time

from django.urls import reverse
from django.utils import timezone

from apps.coordinates.models import Coordinate, CoordinateImage

from .base import BaseTest, make_image


class MapPayloadTest(BaseTest):
    """내려보내는 데이터 자체"""

    def setUp(self):
        super().setUp()
        self.url = reverse('coordinates:map')

    def _markers(self, response):
        """HTML 에 박힌 markers_json 을 꺼낸다"""
        html = response.content.decode()
        m = re.search(r'const markersData = (\[.*?\])\.map\(', html, re.S)
        self.assertIsNotNone(m, 'markersData 를 못 찾았다')
        return json.loads(m.group(1))

    def _labels(self, response):
        html = response.content.decode()
        m = re.search(r'const LABELS = (\{.*?\});', html, re.S)
        self.assertIsNotNone(m, 'LABELS 를 못 찾았다')
        return json.loads(m.group(1))

    def test_승인된_글이_마커로_나온다(self):
        self.make_coord(title='보이는 글')
        self.make_coord(title='대기 중', status=Coordinate.Status.PENDING)
        markers = self._markers(self.client.get(self.url))
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]['t'], '보이는 글')

    def test_사진_주소가_넘어온다(self):
        coord = self.make_coord(title='사진 있음')
        CoordinateImage.objects.create(coordinate=coord, image=make_image(), order=0)
        markers = self._markers(self.client.get(self.url))
        self.assertTrue(markers[0]['m'], '사진 주소가 비었다')

    def test_사진이_없으면_빈_값이다(self):
        self.make_coord(title='사진 없음')
        self.assertIsNone(self._markers(self.client.get(self.url))[0]['m'])

    def test_첫_사진을_쓴다(self):
        coord = self.make_coord()
        CoordinateImage.objects.create(coordinate=coord, image=make_image('a.jpg'), order=0)
        CoordinateImage.objects.create(coordinate=coord, image=make_image('b.jpg'), order=1)
        markers = self._markers(self.client.get(self.url))
        self.assertEqual(len(markers), 1)
        self.assertIn('a', markers[0]['m'])

    def test_이름표는_글마다_넣지_않고_한_번만_보낸다(self):
        """예전에는 category_display·region_display 가 글마다 따라붙었다.
        종류는 4개·십여 개뿐인데 2,523번 반복돼서 HTML 이 790KB 였다."""
        self.make_coord()
        r = self.client.get(self.url)
        markers = self._markers(r)
        labels = self._labels(r)

        for banned in ('category_display', 'region_display'):
            self.assertNotIn(banned, markers[0],
                             '%s 가 글마다 들어 있다' % banned)
        self.assertIn(Coordinate.Category.MUSHROOM, labels['category'])
        self.assertTrue(labels['region'])

    def test_카테고리_필터가_먹는다(self):
        self.make_coord(title='버섯', category=Coordinate.Category.MUSHROOM)
        self.make_coord(title='꽃', category=Coordinate.Category.BIGFLOWER)
        markers = self._markers(
            self.client.get(self.url, {'category': Coordinate.Category.BIGFLOWER}))
        self.assertEqual([m['t'] for m in markers], ['꽃'])

    def test_글이_없어도_터지지_않는다(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._markers(r), [])


class MapQueryTest(BaseTest):
    """N+1 재발 방지 — 이 묶음이 이 화면의 핵심 방어선이다"""

    def setUp(self):
        super().setUp()
        self.url = reverse('coordinates:map')

    def _make(self, n, images_each=1):
        for i in range(n):
            coord = self.make_coord(title='글 %d' % i,
                                    latitude='%.6f' % (35.0 + i * 0.001),
                                    longitude='%.6f' % (129.0 + i * 0.001))
            for k in range(images_each):
                CoordinateImage.objects.create(
                    coordinate=coord, image=make_image('m%d_%d.jpg' % (i, k)), order=k)

    def _query_count(self):
        """첫 요청은 설정·세션을 채우느라 몇 개 더 쓴다. 한 번 돌리고 나서 잰다."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.get(self.url)                 # 예열
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.queries = ctx.captured_queries
        return len(ctx.captured_queries)

    def test_쿼리_수가_글_수에_따라_늘지_않는다(self):
        """예전에는 글 하나마다 `coord.images.first()` 로 한 번씩 물어봤다.
        2,523개에서 쿼리 2,526개 / 1.26초였다."""
        self._make(5)
        few = self._query_count()

        Coordinate.objects.all().delete()
        self._make(40, images_each=2)
        many = self._query_count()

        self.assertEqual(
            few, many,
            '글이 5개일 때 %d개, 40개일 때 %d개 — 글 수에 따라 늘고 있다 (N+1)'
            % (few, many))

    def test_쿼리는_여섯_개를_넘지_않는다(self):
        self._make(30, images_each=2)
        n = self._query_count()
        self.assertLessEqual(n, 6, '쿼리가 %d개다' % n)

    def test_글이_많아도_느려지지_않는다(self):
        """2,500개를 깔아놓고 잰다. 기준은 느슨하게 둔다 — 진짜 방어는 위의
        쿼리 수 테스트고, 이건 '한 자리에서 터지고 있지 않은지' 를 본다."""
        now = timezone.now()
        Coordinate.objects.bulk_create([
            Coordinate(title='글 %d' % i,
                       latitude='%.6f' % (33.0 + (i % 600) * 0.005),
                       longitude='%.6f' % (126.0 + (i % 700) * 0.005),
                       category=Coordinate.Category.MUSHROOM,
                       status=Coordinate.Status.APPROVED, approved_at=now)
            for i in range(2500)
        ], batch_size=500)

        self.client.get(self.url)                 # 첫 호출은 안 잰다
        start = time.perf_counter()
        r = self.client.get(self.url)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(r.status_code, 200)
        self.assertLess(elapsed_ms, 1500,
                        '2,500개에서 %.0fms 걸렸다' % elapsed_ms)

    def test_사진이_많아도_마커_하나당_주소_하나다(self):
        self._make(10, images_each=5)
        markers_html = self.client.get(self.url).content.decode()
        m = re.search(r'const markersData = (\[.*?\])\.map\(', markers_html, re.S)
        markers = json.loads(m.group(1))
        self.assertEqual(len(markers), 10)
        self.assertTrue(all(isinstance(x['m'], str) for x in markers))


class MapClientGuardTest(BaseTest):
    """화면 쪽 안전장치가 템플릿에 실제로 들어 있는지

    여기 하나라도 빠지면 사진 280MB 가 그대로 돌아온다.
    """

    def setUp(self):
        super().setUp()
        self.html = self.client.get(reverse('coordinates:map')).content.decode()

    def test_목록_사진은_lazy로_받는다(self):
        """이게 빠지면 사이트의 모든 사진을 한 번에 내려받는다"""
        self.assertIn('loading="lazy"', self.html)

    def test_목록은_한_번에_다_그리지_않는다(self):
        self.assertIn('const LIST_PAGE', self.html)
        self.assertIn('listMoreBtn', self.html)

    def test_지도_움직임에_debounce가_걸려_있다(self):
        """예전에는 moveend 마다 2,523개를 다시 그렸다"""
        self.assertIn('scheduleListUpdate', self.html)
        self.assertIn("map.on('moveend', scheduleListUpdate)", self.html)
        self.assertNotIn("map.on('moveend', updateList)", self.html)

    def test_마커를_나눠서_넣는다(self):
        """2,500개를 한 번에 넣으면 그 동안 화면이 멈춘다"""
        self.assertIn('chunkedLoading: true', self.html)
        self.assertIn('markerCluster.addLayers(', self.html)

    def test_아이콘은_분류마다_하나만_만든다(self):
        """예전에는 글마다 divIcon 을 새로 만들어 2,523개가 생겼다"""
        self.assertIn('function iconFor(', self.html)
        self.assertIn('sharedIcons', self.html)

    def test_팝업은_누를_때_만든다(self):
        """예전에는 열지도 않는 팝업 HTML 2,523개를 미리 만들어 뒀다"""
        self.assertIn('function popupHtml(', self.html)
        self.assertIn('marker.bindPopup(function ()', self.html)

    def test_제목을_그대로_넣지_않는다(self):
        """목록·팝업을 innerHTML 로 만든다. 제목에 <>" 가 들어가면 깨진다"""
        self.assertIn('function escapeAttr(', self.html)
