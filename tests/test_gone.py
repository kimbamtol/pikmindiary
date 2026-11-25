"""없어졌다는 제보 - 「?」 표식, 찬반, 없어짐 확정

2026-11-25 에 넣었다. 그전에는 「아예 없어졌어요」 제보가 들어와도
운영자 화면에만 쌓였고, 세 가지가 전부 없었다.

1. 목록에서 안 보였다 - 사람들은 글을 안 열고 목록에서 좌표만 복사한다.
   헛걸음을 막으려면 카드에 보여야 한다.
2. 확인해 줄 방법이 없었다 - 다녀온 사람이 「아직 있어요」 할 데가 없었다.
   버섯은 잠깐 사라졌다 5분 뒤에 다시 생기기도 해서, 한 사람 말만으로는
   판단할 수 없다.
3. 확인이 끝나도 적어둘 칸이 없었다 - `is_nerfed`(사진이 조금 달라짐) 뿐이라
   운영자가 「확인 완료」를 눌러도 글은 멀쩡해 보였고, 다음 사람이 또 헛걸음했다.

**여기서 지키는 규칙**

1. 제보가 있는 글에만 「?」가 붙는다. 운영자가 보고 넘긴 제보는 안 센다.
2. 「아직 있어요」는 반대표다. [너프됨] 제보 수에 절대 섞이지 않는다.
3. 한 사람은 한 표다. 마음을 바꾸면 표가 바뀌지, 늘지 않는다.
4. 카드 수가 늘어도 쿼리는 안 늘어난다 (N+1).
5. 「없어짐」으로 확정해도 글은 지우지 않는다. 흐리게 남긴다.
6. 「?」는 글 열기·좌표 복사와 겹치지 않게 JS 가 가로챈다.
"""
import re

from django.urls import reverse

from apps.coordinates.gone import attach_gone_state
from apps.coordinates.models import Coordinate, NerfReport

from .base import BaseTest

LIST = '/coordinates/'
CARD_TPL = 'templates/coordinates/_card_list.html'
LIST_TPL = 'templates/coordinates/list.html'


class GoneBase(BaseTest):
    def report(self, coord, kind, user=None, session='s1'):
        return NerfReport.objects.create(
            coordinate=coord, user=user,
            session_key='' if user else session,
            change_kind=kind, ip_address='10.0.0.1',
        )

    def list_html(self, url=LIST):
        self.client.cookies['pd_w'] = 'mo'
        return self.client.get(url).content.decode()


class MarkShownTest(GoneBase):
    """규칙 1 - 제보가 있는 글에만 「?」"""

    def setUp(self):
        super().setUp()
        self.quiet = self.make_coord(title='멀쩡한 자리')
        self.noisy = self.make_coord(title='없어졌대는 자리')
        self.report(self.noisy, NerfReport.ChangeKind.GONE)

    def test_제보가_있으면_물음표가_붙는다(self):
        html = self.list_html()
        self.assertEqual(html.count('class="gone-q"'), 1, '「?」가 하나여야 한다')
        self.assertTrue('data-gone-pk="%d"' % self.noisy.pk in html)

    def test_제보가_없으면_안_붙는다(self):
        self.noisy.nerf_reports.all().delete()
        self.assertTrue('class="gone-q"' not in self.list_html())

    def test_운영자가_보고_넘긴_제보는_안_센다(self):
        """안 그러면 한 번 처리한 글에 「?」가 영영 붙어 있는다"""
        from django.utils import timezone
        Coordinate.objects.filter(pk=self.noisy.pk).update(
            change_checked_at=timezone.now())
        self.assertTrue('class="gone-q"' not in self.list_html())

    def test_그_뒤에_새_제보가_오면_다시_붙는다(self):
        from django.utils import timezone
        Coordinate.objects.filter(pk=self.noisy.pk).update(
            change_checked_at=timezone.now())
        self.report(self.noisy, NerfReport.ChangeKind.GONE, session='s2')
        self.assertTrue('class="gone-q"' in self.list_html())

    def test_사진이_달라요_는_물음표를_안_붙인다(self):
        """「?」는 없어졌다는 제보 전용이다"""
        self.noisy.nerf_reports.all().delete()
        self.report(self.noisy, NerfReport.ChangeKind.PHOTO)
        self.assertTrue('class="gone-q"' not in self.list_html())

    def test_확정된_글은_제보가_없어도_붙는다(self):
        self.noisy.nerf_reports.all().delete()
        Coordinate.objects.filter(pk=self.noisy.pk).update(is_gone=True)
        html = self.list_html()
        self.assertTrue('class="gone-q"' in html)
        self.assertTrue('coord-gone' in html, '흐리게 하는 표가 없다')


class CountingTest(GoneBase):
    """규칙 2, 3 - 「아직 있어요」는 반대표이고, 한 사람은 한 표"""

    def setUp(self):
        super().setUp()
        self.coord = self.make_coord(title='다툼 있는 자리')

    def test_아직_있어요는_너프_제보_수에_안_들어간다(self):
        user = self.make_user()
        self.client.force_login(user)
        self.client.post(reverse('coordinates:toggle_nerf', args=[self.coord.pk]),
                         {'kind': 'ALIVE'})
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.nerf_report_count, 0,
                         '「아직 있어요」가 제보 수에 섞였다')
        self.assertFalse(self.coord.is_nerfed,
                         '멀쩡하다고 말했는데 [너프됨]이 켜졌다')

    def test_없어졌다는_제보는_제보_수에_들어간다(self):
        user = self.make_user()
        self.client.force_login(user)
        self.client.post(reverse('coordinates:toggle_nerf', args=[self.coord.pk]),
                         {'kind': 'GONE'})
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.nerf_report_count, 1)

    def test_마음을_바꾸면_표가_바뀐다(self):
        user = self.make_user()
        self.client.force_login(user)
        url = reverse('coordinates:toggle_nerf', args=[self.coord.pk])
        self.client.post(url, {'kind': 'GONE'})
        self.client.post(url, {'kind': 'ALIVE'})
        self.assertEqual(NerfReport.objects.filter(coordinate=self.coord).count(), 1,
                         '표가 늘어났다 - 한 사람 한 표여야 한다')
        attach_gone_state([self.coord])
        self.assertEqual((self.coord.gone_n, self.coord.alive_n), (0, 1))

    def test_같은_것을_또_누르면_취소된다(self):
        user = self.make_user()
        self.client.force_login(user)
        url = reverse('coordinates:toggle_nerf', args=[self.coord.pk])
        self.client.post(url, {'kind': 'ALIVE'})
        self.client.post(url, {'kind': 'ALIVE'})
        self.assertEqual(NerfReport.objects.filter(coordinate=self.coord).count(), 0)

    def test_찬반을_따로_센다(self):
        self.report(self.coord, NerfReport.ChangeKind.GONE, session='a')
        self.report(self.coord, NerfReport.ChangeKind.GONE, session='b')
        self.report(self.coord, NerfReport.ChangeKind.ALIVE, session='c')
        attach_gone_state([self.coord])
        self.assertEqual((self.coord.gone_n, self.coord.alive_n), (2, 1))


class NoExtraQueryTest(GoneBase):
    """규칙 4 - 카드가 늘어도 쿼리는 그대로 (N+1 방지)"""

    def test_글이_늘어도_제보_쿼리는_안_는다(self):
        """제보 상태는 글이 몇 개든 쿼리 한 번으로 가져와야 한다.

        목록 전체 쿼리 수로 재면 안 된다 - 카드 썸네일(`coord.images.first`)이
        글마다 한 번씩 묻는 **예전부터 있던** N+1 이 섞여 들어온다.
        그건 이 기능과 상관없는 별개 문제라서, 여기서는 제보 쿼리만 본다.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def nerf_queries(n):
            Coordinate.objects.all().delete()
            for i in range(n):
                c = self.make_coord(title='자리 %02d' % i)
                self.report(c, NerfReport.ChangeKind.GONE, session='s%d' % i)
            self.client.cookies['pd_w'] = 'mo'
            with CaptureQueriesContext(connection) as q:
                self.client.get(LIST)
            return sum(1 for x in q.captured_queries
                       if 'coordinates_nerfreport' in x['sql'])

        few, many = nerf_queries(3), nerf_queries(18)
        self.assertEqual(few, 1, '제보 쿼리가 %d개다 - 한 번에 가져와야 한다' % few)
        self.assertEqual(many, 1, '글이 18개일 때 제보 쿼리가 %d개다' % many)

    def test_상태_붙이기는_쿼리_한_개다(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        coords = [self.make_coord(title='자리 %d' % i) for i in range(10)]
        for i, c in enumerate(coords):
            self.report(c, NerfReport.ChangeKind.GONE, session='q%d' % i)
        with CaptureQueriesContext(connection) as q:
            attach_gone_state(coords)
        self.assertEqual(len(q), 1, '쿼리가 %d개다' % len(q))

    def test_빈_목록에는_묻지도_않는다(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as q:
            attach_gone_state([])
        self.assertEqual(len(q), 0)


class AdminActionTest(GoneBase):
    """규칙 5 - 확정해도 글은 지우지 않는다"""

    def setUp(self):
        super().setUp()
        self.coord = self.make_coord(title='사라진 자리')
        self.report(self.coord, NerfReport.ChangeKind.GONE)
        self.staff = self.make_user(nickname='운영자')
        self.staff.is_staff = True
        self.staff.is_superuser = True
        self.staff.save()
        self.client.force_login(self.staff)
        self.url = reverse('admin_panel:change_apply', args=[self.coord.pk])

    def test_없어짐으로_확정한다(self):
        self.client.post(self.url, {'action': 'gone'})
        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_gone)
        self.assertIsNotNone(self.coord.gone_at)
        self.assertIsNotNone(self.coord.change_checked_at)

    def test_확정해도_글은_안_지운다(self):
        self.client.post(self.url, {'action': 'gone'})
        self.assertTrue(Coordinate.objects.filter(pk=self.coord.pk).exists(),
                        '글이 사라졌다 - 흐리게 남겨야 「살아났어요」 제보를 받는다')
        self.coord.refresh_from_db()
        self.assertEqual(self.coord.status, Coordinate.Status.APPROVED)

    def test_확정해도_너프_표시는_안_켠다(self):
        """없어진 것과 사진이 조금 달라진 것은 다른 이야기다"""
        self.client.post(self.url, {'action': 'gone'})
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_nerfed)

    def test_글쓴이에게_알린다(self):
        from apps.interactions.models import Notification
        author = self.make_user(nickname='글쓴이')
        Coordinate.objects.filter(pk=self.coord.pk).update(author=author)
        self.client.post(self.url, {'action': 'gone'})
        self.assertTrue(Notification.objects.filter(recipient=author).exists())

    def test_없어짐을_풀_수_있다(self):
        self.client.post(self.url, {'action': 'gone'})
        self.report(self.coord, NerfReport.ChangeKind.ALIVE, session='z')
        self.client.post(self.url, {'action': 'alive'})
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_gone)
        self.assertIsNone(self.coord.gone_at)
        self.assertEqual(
            NerfReport.objects.filter(
                coordinate=self.coord,
                change_kind__in=('GONE', 'ALIVE')).count(), 0,
            '없어짐 관련 제보가 남아 있다')

    def test_풀_때_다른_제보는_안_건드린다(self):
        self.report(self.coord, NerfReport.ChangeKind.PHOTO, session='p')
        self.client.post(self.url, {'action': 'alive'})
        self.assertTrue(
            NerfReport.objects.filter(
                coordinate=self.coord,
                change_kind=NerfReport.ChangeKind.PHOTO).exists(),
            '「사진이 달라요」 제보까지 지웠다')

    def test_제보_지우기는_없어짐도_같이_끈다(self):
        self.client.post(self.url, {'action': 'gone'})
        self.client.post(self.url, {'action': 'clear'})
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_gone)
        self.assertIsNone(self.coord.gone_at)


class ClickGuardTest(BaseTest):
    """규칙 6 - 「?」가 글 열기·좌표 복사를 가로채야 한다

    사진 전체가 글 링크이고, 촘촘 보기에서는 사진을 누르면 좌표가 복사된다.
    막지 않으면 「?」를 눌러도 글로 넘어가거나 좌표만 복사된다.
    """

    def _tpl(self, path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_물음표는_button_이다(self):
        """<a> 안에 <a> 를 넣을 수 없고, button 이라야 기본 동작을 막기 쉽다"""
        tpl = self._tpl(CARD_TPL)
        self.assertTrue(re.search(r'<button[^>]*class="gone-q"', tpl),
                        '「?」가 button 이 아니다')

    def test_클릭을_멈춘다(self):
        tpl = self._tpl(LIST_TPL)
        i = tpl.find(".gone-q')")
        self.assertNotEqual(i, -1, '「?」를 잡는 곳이 없다')
        near = tpl[i:i + 500]
        self.assertTrue('preventDefault' in near, 'preventDefault 가 없다 - 글로 넘어간다')
        self.assertTrue('stopPropagation' in near, 'stopPropagation 이 없다 - 좌표가 복사된다')

    def test_문서_단계에서_먼저_잡는다(self):
        """무한 스크롤로 카드가 계속 늘어나므로 카드마다 걸 수 없다.
        게다가 복사 핸들러보다 먼저 받아야 해서 capture 단계라야 한다."""
        tpl = self._tpl(LIST_TPL)
        i = tpl.find(".gone-q')")
        self.assertTrue(re.search(r'\}, true\);', tpl[i:i + 2500]),
                        'capture 단계(true)로 안 걸려 있다')

    def test_여러_줄_주석을_쓰지_않았다(self):
        """{# #} 는 한 줄짜리만 된다. 여러 줄이면 화면에 글자로 찍힌다"""
        tpl = self._tpl(CARD_TPL)
        for m in re.finditer(r'\{#(.*?)#\}', tpl, flags=re.S):
            self.assertTrue('\n' not in m.group(1),
                            '여러 줄 {# #} 주석이 있다: %r' % m.group(1)[:50])
