"""'사진이 달라요' 제보 → 운영자 확인 → 분류 수정

규칙:
- 제보자는 무엇이 달라졌는지(사진만/버섯/빅플/모종/없어짐)까지 고를 수 있다.
- 한 사람의 표는 하나다. 다른 항목을 고르면 표가 늘지 않고 내용만 바뀐다.
- 운영자 목록은 '확인 완료' 이후에 들어온 제보만 보여준다. 여기가 틀리면
  처리한 글이 계속 올라와서 목록을 아예 안 보게 된다.
- 분류를 고치면 사진도 낡은 것이므로 [너프됨]이 같이 붙고, 작성자에게 알림이 간다.
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.coordinates.models import Coordinate, NerfReport
from apps.core.models import SiteSettings
from apps.interactions.models import Notification

from .base import BaseTest

Kind = NerfReport.ChangeKind


class ChangeReportTest(BaseTest):
    """제보자 쪽"""

    def setUp(self):
        super().setUp()
        s = SiteSettings.get_settings()
        s.nerf_threshold = 3
        s.nerf_window_days = 7
        s.save()
        self.owner = self.make_user(nickname='글쓴이')
        self.coord = self.make_coord(author=self.owner, category=Coordinate.Category.BIGFLOWER)
        self.url = reverse('coordinates:toggle_nerf', args=[self.coord.pk])

    def test_무엇이_달라졌는지_같이_저장된다(self):
        self.login(self.make_user())
        self.client.post(self.url, {'kind': 'MUSHROOM'})

        r = NerfReport.objects.get()
        self.assertEqual(r.change_kind, Kind.MUSHROOM)
        self.assertEqual(r.suggested_category, Coordinate.Category.MUSHROOM)

    def test_항목을_안_고르면_사진만_달라요로_들어간다(self):
        self.login(self.make_user())
        self.client.post(self.url)
        self.assertEqual(NerfReport.objects.get().change_kind, Kind.PHOTO)

    def test_이상한_값을_보내도_사진만_달라요로_떨어진다(self):
        self.login(self.make_user())
        self.client.post(self.url, {'kind': 'DROP TABLE'})
        self.assertEqual(NerfReport.objects.get().change_kind, Kind.PHOTO)

    def test_다른_항목을_고르면_표는_그대로_내용만_바뀐다(self):
        self.login(self.make_user())
        self.client.post(self.url, {'kind': 'MUSHROOM'})
        res = self.client.post(self.url, {'kind': 'SEEDLING'})

        self.assertEqual(NerfReport.objects.count(), 1)
        self.assertEqual(NerfReport.objects.get().change_kind, Kind.SEEDLING)
        self.assertTrue(res.json()['reported'])

    def test_같은_항목을_다시_누르면_취소된다(self):
        self.login(self.make_user())
        self.client.post(self.url, {'kind': 'MUSHROOM'})
        res = self.client.post(self.url, {'kind': 'MUSHROOM'})

        self.assertEqual(NerfReport.objects.count(), 0)
        self.assertFalse(res.json()['reported'])

    def test_사진만_달라요도_너프_집계에_들어간다(self):
        for kind in ('PHOTO', 'MUSHROOM', 'GONE'):
            user = self.make_user()
            self.client.force_login(user)
            self.client.post(self.url, {'kind': kind})
            self.client.logout()

        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_nerfed)

    def test_비회원도_항목을_고를_수_있다(self):
        self.client.post(self.url, {'kind': 'BIGFLOWER'})
        r = NerfReport.objects.get()
        self.assertIsNone(r.user)
        self.assertEqual(r.change_kind, Kind.BIGFLOWER)

    def test_상세화면에_선택지가_나온다(self):
        html = self.client.get(reverse('coordinates:detail', args=[self.coord.pk])).content.decode()
        self.assertIn('무엇이 달라졌나요', html)
        self.assertIn('버섯이 됐어요', html)
        self.assertIn('data-kind="GONE"', html)


class ChangeAdminTest(BaseTest):
    """운영자 쪽"""

    def setUp(self):
        super().setUp()
        self.staff = self.make_user(nickname='운영자', is_staff=True)
        self.owner = self.make_user(nickname='글쓴이')
        self.coord = self.make_coord(author=self.owner, category=Coordinate.Category.BIGFLOWER)
        self.list_url = reverse('admin_panel:change_list')
        self.apply_url = reverse('admin_panel:change_apply', args=[self.coord.pk])

    def report(self, kind=Kind.MUSHROOM, user=None, **kw):
        return NerfReport.objects.create(
            coordinate=self.coord,
            user=user or self.make_user(),
            change_kind=kind,
            **kw
        )

    def test_운영자가_아니면_못_본다(self):
        self.login(self.make_user())
        res = self.client.get(self.list_url)
        self.assertNotEqual(res.status_code, 200)

    def test_제보가_모여서_보인다(self):
        self.report(Kind.MUSHROOM)
        self.report(Kind.MUSHROOM)
        self.report(Kind.PHOTO)

        self.login(self.staff)
        html = self.client.get(self.list_url).content.decode()
        self.assertIn(self.coord.title, html)
        self.assertIn('버섯이 됐어요', html)
        # 표를 가장 많이 받은 분류를 제안한다
        self.assertIn('분류를 버섯(으)로 변경', html)

    def test_확인_완료를_누르면_목록에서_빠진다(self):
        self.report()
        self.login(self.staff)

        self.client.post(self.apply_url, {'action': 'done'})
        self.coord.refresh_from_db()
        self.assertIsNotNone(self.coord.change_checked_at)

        html = self.client.get(self.list_url).content.decode()
        self.assertNotIn(self.coord.title, html)

    def test_확인_완료_뒤에_새_제보가_오면_다시_올라온다(self):
        self.report()
        self.login(self.staff)
        self.client.post(self.apply_url, {'action': 'done'})

        self.report(Kind.SEEDLING)          # 새 제보
        html = self.client.get(self.list_url).content.decode()
        self.assertIn(self.coord.title, html)

    def test_분류를_바꾸면_너프표시와_알림이_같이_붙는다(self):
        self.report(Kind.MUSHROOM)
        self.login(self.staff)

        self.client.post(self.apply_url, {'action': 'category', 'category': 'MUSHROOM'})

        self.coord.refresh_from_db()
        self.assertEqual(self.coord.category, Coordinate.Category.MUSHROOM)
        self.assertTrue(self.coord.is_nerfed)            # 사진은 낡은 것이므로
        self.assertIsNotNone(self.coord.change_checked_at)

        note = Notification.objects.filter(recipient=self.owner).first()
        self.assertIsNotNone(note)
        self.assertIn('버섯', note.message)

    def test_없는_분류로는_못_바꾼다(self):
        self.report()
        self.login(self.staff)
        self.client.post(self.apply_url, {'action': 'category', 'category': 'DRAGON'})

        self.coord.refresh_from_db()
        self.assertEqual(self.coord.category, Coordinate.Category.BIGFLOWER)

    def test_제보_지우기는_표시까지_끈다(self):
        self.report()
        Coordinate.objects.filter(pk=self.coord.pk).update(is_nerfed=True, nerf_report_count=1)
        self.login(self.staff)

        self.client.post(self.apply_url, {'action': 'clear'})
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_nerfed)
        self.assertEqual(NerfReport.objects.count(), 0)

    def test_오래된_제보_일괄_정리(self):
        self.report()
        NerfReport.objects.update(created_at=timezone.now() - timedelta(days=100))
        fresh = self.make_coord(author=self.owner, title='최근 글')
        NerfReport.objects.create(coordinate=fresh, user=self.make_user())

        self.login(self.staff)
        self.client.post(reverse('admin_panel:change_sweep'), {'days': 30})

        self.coord.refresh_from_db()
        fresh.refresh_from_db()
        self.assertIsNotNone(self.coord.change_checked_at)   # 100일 전 → 내려감
        self.assertIsNone(fresh.change_checked_at)           # 오늘 것 → 남는다

    def test_분류_제보가_현재_분류와_같으면_제안하지_않는다(self):
        self.report(Kind.BIGFLOWER)      # 이미 빅플라워인 글
        self.login(self.staff)
        html = self.client.get(self.list_url).content.decode()
        self.assertNotIn('분류를 빅플라워(으)로 변경', html)

    def test_대시보드에_개수가_나온다(self):
        self.report()
        self.login(self.staff)
        html = self.client.get(reverse('admin_panel:dashboard')).content.decode()
        self.assertIn('엽서 변경 제보', html)
