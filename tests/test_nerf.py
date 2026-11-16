"""엽서 바뀜(너프) 제보

규칙: 정해진 기간(기본 7일) 안에 기준 인원(기본 3명)이 제보하면 제목 앞에 [너프됨]이 붙는다.
비회원도 한 표를 갖고, 같은 사람은 두 번 세지 않는다.
기간이 지난 제보는 집계에서 빠져야 한다 - 여기가 틀리면 한 번 붙은 표시가 영원히 남는다.
"""
import re
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.coordinates.models import Coordinate, NerfReport
from apps.core.models import SiteSettings

from .base import BaseTest

BADGE = re.compile(r'<span class="nerf-badge">\[너프됨\]</span>')


class NerfTest(BaseTest):
    def setUp(self):
        super().setUp()
        s = SiteSettings.get_settings()
        s.nerf_threshold = 3
        s.nerf_window_days = 7
        s.save()
        self.owner = self.make_user(nickname='글쓴이')
        self.coord = self.make_coord(author=self.owner)
        self.url = reverse('coordinates:toggle_nerf', args=[self.coord.pk])

    def report_by_new_user(self):
        client_user = self.make_user()
        self.client.force_login(client_user)
        self.client.post(self.url)
        self.client.logout()
        return client_user

    def test_제보를_눌렀다_취소한다(self):
        self.login(self.make_user())
        self.client.post(self.url)
        self.assertEqual(NerfReport.objects.count(), 1)

        self.client.post(self.url)
        self.assertEqual(NerfReport.objects.count(), 0)

    def test_같은_사람이_두_번_세어지지_않는다(self):
        user = self.login(self.make_user())
        self.client.post(self.url)
        self.client.post(self.url)       # 취소
        self.client.post(self.url)       # 다시 제보
        self.assertEqual(NerfReport.objects.filter(user=user).count(), 1)

    def test_기준_인원을_채우면_표시가_붙는다(self):
        for _ in range(2):
            self.report_by_new_user()
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_nerfed)

        self.report_by_new_user()        # 세 번째
        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed)
        self.assertIsNotNone(self.coord.nerfed_at)

    def test_제목_자체는_바뀌지_않는다(self):
        for _ in range(3):
            self.report_by_new_user()
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.title, '테스트 좌표')
        self.assertNotIn('너프', self.coord.title)

    def test_표시가_붙으면_화면에_배지가_나온다(self):
        html = self.client.get(reverse('coordinates:detail', args=[self.coord.pk])).content.decode()
        self.assertEqual(len(BADGE.findall(html)), 0)

        for _ in range(3):
            self.report_by_new_user()

        html = self.client.get(reverse('coordinates:detail', args=[self.coord.pk])).content.decode()
        self.assertEqual(len(BADGE.findall(html)), 1)

    def test_기간이_지난_제보는_세지_않는다(self):
        for _ in range(2):
            self.report_by_new_user()
        # 두 건을 10일 전으로 돌려놓는다
        old = timezone.now() - timedelta(days=10)
        NerfReport.objects.update(created_at=old)

        self.report_by_new_user()        # 최근 1건뿐
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_nerfed)

    def test_비회원도_제보할_수_있다(self):
        self.client.post(self.url)
        self.assertEqual(NerfReport.objects.count(), 1)
        self.assertIsNone(NerfReport.objects.get().user)

    def test_작성자는_표시를_해제할_수_있다(self):
        for _ in range(3):
            self.report_by_new_user()
        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed)

        self.login(self.owner)
        self.client.post(reverse('coordinates:clear_nerf', args=[self.coord.pk]))
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_nerfed)
        self.assertEqual(NerfReport.objects.count(), 0)   # 제보도 같이 정리된다

    def test_남은_해제할_수_없다(self):
        for _ in range(3):
            self.report_by_new_user()
        self.login(self.make_user(nickname='남'))
        self.client.post(reverse('coordinates:clear_nerf', args=[self.coord.pk]))

        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed)

    def test_기준_인원을_바꾸면_바로_반영된다(self):
        s = SiteSettings.get_settings()
        s.nerf_threshold = 1
        s.save()

        self.report_by_new_user()
        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed)
