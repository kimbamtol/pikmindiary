"""엽서 바뀜(너프) 제보

규칙: 정해진 기간(기본 7일) 안에 기준 인원(기본 3명)이 제보하면 제목 앞에 [너프됨]이 붙는다.
비회원도 한 표를 갖고, 같은 사람은 두 번 세지 않는다.
기간이 지난 제보는 집계에서 빠져야 한다 - 여기가 틀리면 아직 안 붙은 표시가 잘못 붙는다.

**자동 계산은 켜기만 한다.** 한 번 붙은 표시를 끄는 길은 두 개뿐이다 -
작성자의 해제(clear_nerf), 운영자의 「제보 지우고 표시 끄기」(change_apply 의 clear).
2026-11-18 전에는 제보가 들어올 때마다 기준으로 다시 계산해서 덮어썼고,
그래서 운영자가 손으로 켜둔 표시가 제보 한 건 때문에 도로 꺼졌다.
"""
import re
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.coordinates.models import Coordinate, NerfReport
from apps.core.models import SiteSettings

from .base import BaseTest

BADGE = re.compile(r'<span class="nerf-badge">\[너프됨\]</span>')


class NerfBase(BaseTest):
    """재료만 차린다. 테스트는 아래 두 묶음이 나눠 갖는다"""

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


class NerfTest(NerfBase):
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


class NerfStickyTest(NerfBase):
    """한 번 붙은 표시는 제보 때문에 꺼지지 않는다 - 2026-11-18

    실제로 당한 사고: 2026-11-17 에 운영자가 제보를 보고 93개에 표시를 켰는데,
    그중 #1606(멘카우레 피라미드) 하나가 그날 저녁 새 제보를 받고 도로 꺼졌다.
    제보가 10-30 / 11-05 / 11-17 로 흩어져 있어서 "최근 7일" 창에는 1건뿐이라
    1 < 3 으로 계산된 것이다. 제보가 늘었는데 표시가 사라졌다.
    """

    def test_운영자가_켠_표시는_새_제보로_꺼지지_않는다(self):
        """제보 1건은 기준(3건)에 한참 못 미치지만, 켜둔 것을 끄면 안 된다"""
        Coordinate.objects.filter(pk=self.coord.pk).update(is_nerfed=True)

        self.report_by_new_user()

        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed,
                        '제보가 들어왔는데 표시가 꺼졌다')

    def test_오래된_제보만_남아도_꺼지지_않는다(self):
        """#1606 과 똑같은 모양 - 예전 제보 2건은 창 밖, 새 제보 1건만 창 안"""
        for _ in range(2):
            self.report_by_new_user()
        NerfReport.objects.update(created_at=timezone.now() - timedelta(days=10))
        Coordinate.objects.filter(pk=self.coord.pk).update(is_nerfed=True)

        self.report_by_new_user()

        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed)
        self.assertEqual(self.coord.nerf_report_count, 3)   # 집계는 그대로 센다

    def test_한_명이_제보를_취소해도_꺼지지_않는다(self):
        last = None
        for _ in range(3):
            last = self.report_by_new_user()
        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed)

        self.client.force_login(last)
        self.client.post(self.url)          # 같은 걸 또 누르면 취소
        self.client.logout()

        self.coord.refresh_from_db()
        self.assertEqual(NerfReport.objects.count(), 2)
        self.assertTrue(self.coord.is_nerfed, '취소 한 건에 표시가 꺼졌다')

    def test_끄는_길은_그대로_남아_있다(self):
        """자동으로 안 꺼지는 대신, 사람이 끄는 두 길은 반드시 살아 있어야 한다"""
        Coordinate.objects.filter(pk=self.coord.pk).update(is_nerfed=True)
        self.report_by_new_user()

        self.login(self.owner)
        self.client.post(reverse('coordinates:clear_nerf', args=[self.coord.pk]))
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_nerfed)
        self.assertEqual(NerfReport.objects.count(), 0)

    def test_처음_붙을_때_알림은_한_번만_간다(self):
        """켜진 채로 제보가 또 들어와도 작성자에게 또 알리면 안 된다"""
        from apps.interactions.models import Notification

        for _ in range(3):
            self.report_by_new_user()
        n = Notification.objects.filter(
            recipient=self.owner,
            notification_type=Notification.NotificationType.NERF).count()
        self.assertEqual(n, 1)

        self.report_by_new_user()
        again = Notification.objects.filter(
            recipient=self.owner,
            notification_type=Notification.NotificationType.NERF).count()
        self.assertEqual(again, 1, '표시가 이미 켜져 있는데 또 알렸다')
