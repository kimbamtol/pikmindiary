"""중복 글 막기 — '이 근처에 올라온 글' + 지연율

왜 만들었나:
  같은 엽서를 모르고 또 올리는 글이 꽤 많다. 그런데 **좌표만으로는 중복인지
  알 수 없다** — 시부야 치이카와·K-BOOKS 는 0.0m 거리에 서로 다른 엽서가 3장이고,
  제목도 못 믿는다 (같은 엽서를 서로 다르게 적은 글이 152쌍 있었다).
  그래서 막지도, 경고하지도 않는다. 사진을 보여주고 올리는 사람이 판단한다.

여기서 지키는 것:
  1. 300m 안의 승인된 글만, 가까운 순으로 최대 8개
  2. 잘못된 입력에 500 이 아니라 빈 목록 (글 쓰는 화면이다)
  3. **쿼리 3개 이하, 응답 4KB 이하** — 타이핑 중에 부르는 주소라 여기가 뚫리면
     글 쓰다가 렉이 걸린다. 사진이 많은 글 8개를 보내도 쿼리가 늘면 안 된다.
"""
import time

from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.coordinates.models import Coordinate, CoordinateImage

from .base import BaseTest, make_image

# 서울 강남역 근처. 위도 1도 ≈ 111.3km 이므로 0.001도 ≈ 111m 다.
BASE_LAT = 37.498095
BASE_LNG = 127.027610


class NearbyTest(BaseTest):
    url = None

    def setUp(self):
        super().setUp()
        self.url = reverse('coordinates:nearby')

    def _at(self, dlat=0.0, dlng=0.0, **kw):
        return self.make_coord(
            latitude='%.6f' % (BASE_LAT + dlat),
            longitude='%.6f' % (BASE_LNG + dlng),
            **kw
        )

    def _get(self, lat=BASE_LAT, lng=BASE_LNG, **params):
        q = {'lat': lat, 'lng': lng}
        q.update(params)
        return self.client.get(self.url, q)

    # ── 무엇을 찾나 ────────────────────────────────────────

    def test_근처_글을_찾는다(self):
        self._at(title='같은 자리')
        data = self._get().json()
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['title'], '같은 자리')
        self.assertEqual(data['items'][0]['distance_m'], 0)

    def test_300m_밖은_안_찾는다(self):
        self._at(dlat=0.0045, title='500m 쯤')      # 약 500m
        self.assertEqual(self._get().json()['items'], [])

    def test_300m_안은_찾는다(self):
        self._at(dlat=0.0018, title='200m 쯤')      # 약 200m
        items = self._get().json()['items']
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(items[0]['distance_m'], 200, delta=15)

    def test_가까운_순으로_나온다(self):
        self._at(dlat=0.0020, title='먼 것')
        self._at(dlat=0.0005, title='가까운 것')
        self._at(dlat=0.0012, title='중간')
        titles = [i['title'] for i in self._get().json()['items']]
        self.assertEqual(titles, ['가까운 것', '중간', '먼 것'])

    def test_승인_안_된_글은_안_보인다(self):
        self._at(title='대기 중', status=Coordinate.Status.PENDING)
        self.assertEqual(self._get().json()['items'], [])

    def test_많아도_여덟개까지만_보낸다(self):
        for i in range(14):
            self._at(dlng=0.00002 * i, title='글%d' % i)
        data = self._get().json()
        self.assertEqual(len(data['items']), 8)
        self.assertEqual(data['total'], 14)     # 찾은 건 14개라고 알려준다

    def test_엽서이름이_있으면_그걸_쓴다(self):
        """제목은 사람마다 다르게 적는다. 엽서이름이 있으면 그게 더 정확하다"""
        self._at(title='강남역 2번출구', postcard_name='고양이 엽서')
        self.assertEqual(self._get().json()['items'][0]['title'], '고양이 엽서')

    def test_사진이_있으면_주소를_같이_보낸다(self):
        coord = self._at(title='사진 있음')
        CoordinateImage.objects.create(coordinate=coord, image=make_image(), order=0)
        item = self._get().json()['items'][0]
        self.assertTrue(item['thumb'].startswith('/media/'), item['thumb'])

    def test_사진이_없으면_빈_주소다(self):
        self._at(title='사진 없음')
        self.assertEqual(self._get().json()['items'][0]['thumb'], '')

    def test_너프_표시가_넘어온다(self):
        self._at(title='바뀐 엽서', is_nerfed=True)
        self.assertTrue(self._get().json()['items'][0]['is_nerfed'])

    # ── 500m 까지 더 보기 ──────────────────────────────────

    def test_500m로_넓히면_더_찾는다(self):
        self._at(dlat=0.0040, title='440m 쯤')
        self.assertEqual(self._get().json()['items'], [])
        wide = self._get(r=500).json()
        self.assertEqual(len(wide['items']), 1)
        self.assertEqual(wide['radius_m'], 500)

    def test_500m가_한계다(self):
        """주소를 고쳐 5km 를 달라고 해도 500m 로 자른다"""
        self._at(dlat=0.0300, title='3km 쯤')
        data = self._get(r=5000).json()
        self.assertEqual(data['radius_m'], 500)
        self.assertEqual(data['items'], [])

    def test_넓힐_수_있는지_알려준다(self):
        self.assertTrue(self._get().json()['can_widen'])
        self.assertFalse(self._get(r=500).json()['can_widen'])

    # ── 잘못된 입력 ────────────────────────────────────────

    def test_값이_없어도_500이_아니다(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['items'], [])

    def test_숫자가_아니어도_500이_아니다(self):
        for bad in [{'lat': 'abc', 'lng': '1'}, {'lat': '', 'lng': ''},
                    {'lat': '37.5'}, {'lat': 'nan', 'lng': 'nan'}]:
            with self.subTest(bad):
                r = self.client.get(self.url, bad)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()['items'], [])

    def test_범위를_벗어난_좌표는_빈_목록(self):
        r = self._get(lat=999, lng=999)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['items'], [])

    def test_반경이_숫자가_아니어도_기본값으로_돈다(self):
        self._at(title='근처')
        data = self._get(r='많이').json()
        self.assertEqual(data['radius_m'], 300)
        self.assertEqual(len(data['items']), 1)

    def test_post는_막는다(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_극지방에서도_터지지_않는다(self):
        """위도 90 에서 cos 가 0 이 되면 경도 범위가 무한이 된다"""
        r = self._get(lat=89.999, lng=0)
        self.assertEqual(r.status_code, 200)

    # ── 지연율: 여기가 뚫리면 글 쓰다가 렉이 걸린다 ──────────

    def test_쿼리는_세_개를_넘지_않는다(self):
        """사진이 많은 글이 여럿이어도 쿼리 수가 늘면 안 된다 (N+1 금지)"""
        for i in range(10):
            coord = self._at(dlng=0.00002 * i, title='글%d' % i)
            for k in range(3):
                CoordinateImage.objects.create(
                    coordinate=coord, image=make_image('p%d_%d.jpg' % (i, k)), order=k)

        with self.assertNumQueries(3):
            r = self._get()
        self.assertEqual(len(r.json()['items']), 8)

    def test_응답이_4kb를_넘지_않는다(self):
        """타이핑 중에 부르는 주소다. 커지면 휴대폰 데이터로 체감된다"""
        for i in range(12):
            coord = self._at(dlng=0.00002 * i,
                             title='아주 긴 제목을 가진 엽서 좌표 글 %d' % i)
            CoordinateImage.objects.create(
                coordinate=coord, image=make_image('t%d.jpg' % i), order=0)
        r = self._get()
        self.assertLessEqual(len(r.content), 4096,
                             '응답이 %dB 다' % len(r.content))

    def test_글이_많아도_느려지지_않는다(self):
        """3,000개를 깔아놓고 잰다. 네모(위·경도) 인덱스가 빠지면 여기서 걸린다.

        기준을 느슨하게 둔 이유: 테스트 기계 상태에 따라 흔들린다.
        진짜 방어는 위의 쿼리 수 테스트고, 이건 '전체를 훑고 있지 않은지' 를 본다.
        """
        now = timezone.now()
        bulk = []
        for i in range(3000):
            # 전국에 흩뿌린다 (네모 안에 안 들어오는 것들)
            bulk.append(Coordinate(
                title='먼 글 %d' % i,
                latitude='%.6f' % (33.0 + (i % 600) * 0.005),
                longitude='%.6f' % (126.0 + (i % 700) * 0.005),
                category=Coordinate.Category.MUSHROOM,
                status=Coordinate.Status.APPROVED,
                approved_at=now,
            ))
        Coordinate.objects.bulk_create(bulk, batch_size=500)
        for i in range(5):
            self._at(dlng=0.00002 * i, title='근처 %d' % i)

        self._get()                       # 캐시·연결 준비 (첫 호출은 안 잰다)
        start = time.perf_counter()
        r = self._get()
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(len(r.json()['items']), 5)
        self.assertLess(elapsed_ms, 500,
                        '3,000개에서 %.0fms 걸렸다 — 인덱스를 확인해라' % elapsed_ms)


class NearbyFormTest(BaseTest):
    """글 올리기 화면에 실제로 붙어 있는지"""

    def test_글쓰기_화면에_칸이_있다(self):
        html = self.client.get(reverse('coordinates:create')).content.decode()
        self.assertIn('id="nearbyBox"', html)
        self.assertIn(reverse('coordinates:nearby'), html)

    def test_수정_화면에는_붙이지_않는다(self):
        """이미 올라간 글을 고치는 중이다. 자기 글이 중복으로 떠봐야 방해만 된다"""
        coord = self.make_coord(author=self.login())
        html = self.client.get(reverse('coordinates:edit', args=[coord.pk])).content.decode()
        self.assertNotIn('id="nearbyBox"', html)

    def test_사진은_lazy로_받는다(self):
        html = self.client.get(reverse('coordinates:create')).content.decode()
        self.assertIn("img.loading = 'lazy'", html)

    def test_타이핑_한_글자마다_부르지_않는다(self):
        """400ms 쉬고 나서 한 번만 부른다"""
        html = self.client.get(reverse('coordinates:create')).content.decode()
        self.assertIn('setTimeout(nearbyFetch, 400)', html)

    def test_먼저_부른_것을_끊는다(self):
        html = self.client.get(reverse('coordinates:create')).content.decode()
        self.assertIn('AbortController', html)
