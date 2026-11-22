"""목록 넘기기 방식 - 쪽수 보기와 이어보기

2026-11-22 에 넣었다(건의 #30). 그전에는 무한 스크롤만 있었고 세 가지가 문제였다.

1. 돌아갈 자리를 sessionStorage 에 적어서 탭을 닫으면 지워졌다.
   2,630장을 12장씩 보면 220쪽이라, 보던 데로 가려면 한참 내려야 했다.
2. 돌아올 때 2쪽부터 N쪽까지를 한꺼번에 다시 받았다. 30쪽이면 요청 29개가
   동시에 나갔다. 깊이 본 사람일수록 돌아오기가 느렸다.
3. 검색엔진이 첫 쪽밖에 못 봤다.

쪽수 보기를 기본으로 두면 ?page=N 이 주소에 박혀서 1·2·3 이 전부 사라진다.
무한 스크롤은 고른 사람에게만 남는다.

**여기서 지키는 규칙**

1. 기본은 쪽수 보기다. 아무 설정도 없는 사람은 쪽번호 줄을 본다.
2. 고른 방식은 남는다 - 회원은 계정, 비회원은 쿠키.
3. 한 쪽 장수는 화면 폭이 정한다. 어느 밀도에서도 마지막 줄에 이가 빠지면 안 된다.
4. 없는 쪽을 달라고 해도 500 이 나면 안 된다.
5. 쪽을 넘겨도 검색어·분류·정렬이 따라간다.
6. 두 방식이 한 화면에 같이 나오면 안 된다.
7. 넘기기 버튼에 density-btn 을 같이 붙이면 안 된다 - 실제로 당했다.
   base.html 의 밀도 핸들러가 먼저 집어가서 'on' 을 붙여버리고,
   그러면 넘기기 핸들러가 '이미 켜져 있네' 하고 그냥 돌아간다.
   tests/test_pikmin.py 의 ClassNameCollisionTest 와 같은 종류의 사고다.
"""
import re

from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.core.context_processors import PAGE_SIZE_PC, PAGE_SIZE_NARROW

from .base import BaseTest

LIST = '/coordinates/'
TPL = 'templates/coordinates/list.html'


class PagingBase(BaseTest):
    def make_many(self, n):
        for i in range(n):
            self.make_coord(title='엽서 %03d' % i)

    def get(self, url=LIST, wide=False, **kw):
        self.client.cookies['pd_w'] = 'pc' if wide else 'mo'
        return self.client.get(url, **kw)

    def cards(self, resp):
        return resp.content.decode().count('class="card coord-card"')

    def html(self, resp):
        return resp.content.decode()


class DefaultModeTest(PagingBase):
    """규칙 1, 6 - 기본은 쪽수 보기이고 두 방식이 섞이지 않는다"""

    def setUp(self):
        super().setUp()
        self.make_many(PAGE_SIZE_NARROW + 5)

    def test_아무_설정도_없으면_쪽번호_줄을_본다(self):
        html = self.html(self.get())
        self.assertTrue('class="pagination"' in html, '쪽번호 줄이 없다')
        self.assertTrue('id="scroll-sentinel"' not in html,
                        '쪽수 보기인데 무한 스크롤 감지기가 같이 있다')

    def test_이어보기를_고르면_감지기만_남는다(self):
        self.client.cookies['pd_paging'] = 'scroll'
        html = self.html(self.get())
        self.assertTrue('id="scroll-sentinel"' in html, '감지기가 없다')
        self.assertTrue('class="pagination"' not in html,
                        '이어보기인데 쪽번호 줄이 같이 있다')

    def test_한_쪽뿐이면_쪽번호_줄을_안_그린다(self):
        Coordinate = self.make_coord().__class__
        Coordinate.objects.all().delete()
        self.make_coord(title='하나뿐')
        self.assertTrue('class="pagination"' not in self.html(self.get()))


class PageSizeTest(PagingBase):
    """규칙 3 - 화면 폭이 한 쪽 장수를 정한다"""

    def setUp(self):
        super().setUp()
        self.make_many(PAGE_SIZE_PC + 10)

    def test_PC_는_서른장(self):
        self.assertEqual(self.cards(self.get(wide=True)), PAGE_SIZE_PC)

    def test_좁은_화면은_스물네장(self):
        self.assertEqual(self.cards(self.get(wide=False)), PAGE_SIZE_NARROW)

    def test_쿠키가_없으면_좁은_쪽으로_친다(self):
        # 첫 방문과 검색엔진. 넘치는 것보다 모자란 게 낫다.
        self.client.cookies.pop('pd_w', None)
        self.assertEqual(self.cards(self.client.get(LIST)), PAGE_SIZE_NARROW)

    def test_줄이_딱_떨어진다(self):
        """어느 밀도에서도 마지막 줄에 이가 빠지면 안 된다.

        칸 수는 list.html 의 @media 가 정한다.
        PC(1100 이상)  크게 2 / 보통 3 / 촘촘 5
        좁은 화면       크게 1 / 보통 2 / 촘촘 3 또는 4
        """
        for cols in (2, 3, 5):
            self.assertEqual(PAGE_SIZE_PC % cols, 0,
                             'PC %d장은 %d열에서 줄이 안 맞는다' % (PAGE_SIZE_PC, cols))
        for cols in (1, 2, 3, 4):
            self.assertEqual(PAGE_SIZE_NARROW % cols, 0,
                             '좁은 화면 %d장은 %d열에서 줄이 안 맞는다'
                             % (PAGE_SIZE_NARROW, cols))


class BadPageTest(PagingBase):
    """규칙 4 - 이상한 쪽 번호를 받아도 멀쩡해야 한다"""

    def setUp(self):
        super().setUp()
        self.make_many(PAGE_SIZE_NARROW * 2 + 3)   # 3쪽

    def _page_of(self, html):
        m = re.search(r'가운데 (\d+) / (\d+) 쪽', html)
        return (int(m.group(1)), int(m.group(2))) if m else (None, None)

    def test_없는_쪽을_달라고_하면_마지막_쪽을_준다(self):
        r = self.get(LIST + '?page=99999')
        self.assertEqual(r.status_code, 200)
        cur, last = self._page_of(self.html(r))
        self.assertEqual(cur, last)
        self.assertEqual(self.cards(r), 3)          # 마지막 쪽 나머지

    def test_음수와_0은_첫_쪽이다(self):
        for bad in ('-5', '0'):
            cur, _ = self._page_of(self.html(self.get(LIST + '?page=' + bad)))
            self.assertEqual(cur, 1, '%s 쪽이 1쪽으로 안 왔다' % bad)

    def test_글자는_첫_쪽이다(self):
        r = self.get(LIST + '?page=abc')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._page_of(self.html(r))[0], 1)

    def test_쪽마다_다른_엽서가_나온다(self):
        a = self.html(self.get(LIST + '?page=1'))
        b = self.html(self.get(LIST + '?page=2'))
        self.assertTrue('엽서 000' in a or '엽서 050' in a)
        self.assertNotEqual(
            re.findall(r'엽서 \d{3}', a)[:3],
            re.findall(r'엽서 \d{3}', b)[:3],
            '1쪽과 2쪽에 같은 엽서가 나온다')


class KeepFiltersTest(PagingBase):
    """규칙 5 - 쪽을 넘겨도 검색어와 분류가 따라간다"""

    def setUp(self):
        super().setUp()
        Coordinate = self.make_coord(title='버림').__class__
        Coordinate.objects.all().delete()
        for i in range(PAGE_SIZE_NARROW + 5):
            self.make_coord(title='버섯 %03d' % i,
                            category=Coordinate.Category.MUSHROOM)
        for i in range(5):
            self.make_coord(title='모종 %03d' % i,
                            category=Coordinate.Category.SEEDLING)

    def test_분류와_정렬이_다음_쪽_링크에_남는다(self):
        html = self.html(self.get(LIST + '?category=MUSHROOM&sort=oldest'))
        nxt = re.search(r'<a href="([^"]*)" rel="next"', html)
        self.assertIsNotNone(nxt, '다음 링크가 없다')
        href = nxt.group(1)
        self.assertTrue('category=MUSHROOM' in href, href)
        self.assertTrue('sort=oldest' in href, href)
        self.assertTrue('page=2' in href, href)

    def test_거른_결과만_센다(self):
        # 모종은 5장뿐이라 한 쪽으로 끝난다 - 쪽번호 줄도 장수 줄도 안 나온다
        r = self.get(LIST + '?category=SEEDLING')
        self.assertEqual(self.cards(r), 5, '모종 5장만 나와야 한다')
        self.assertTrue('class="pagination"' not in self.html(r))

        # 버섯은 29장이라 두 쪽이고, 이때는 전체 수를 적어준다
        html = self.html(self.get(LIST + '?category=MUSHROOM'))
        self.assertTrue('전체 %d장' % (PAGE_SIZE_NARROW + 5) in html,
                        '버섯만 세야 하는데 숫자가 다르다')

    def test_검색어가_있어도_안_깨진다(self):
        r = self.get(LIST + '?q=%EB%B2%84%EC%84%AF&page=2')
        self.assertEqual(r.status_code, 200)
        self.assertTrue('버섯' in self.html(r))


class RememberChoiceTest(PagingBase):
    """규칙 2 - 고른 방식이 남는다"""

    def setUp(self):
        super().setUp()
        self.make_many(PAGE_SIZE_NARROW + 5)
        self.url = reverse('core:set_list_paging')

    def test_비회원은_쿠키에_남는다(self):
        r = self.client.post(self.url, {'paging': 'scroll'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.cookies['pd_paging'].value, 'scroll')
        self.assertTrue('id="scroll-sentinel"' in self.html(self.get()))

    def test_회원은_계정에_남는다(self):
        user = self.login()
        self.client.post(self.url, {'paging': 'scroll'})
        user.refresh_from_db()
        self.assertEqual(user.list_paging, 'scroll')

    def test_계정_설정이_쿠키를_이긴다(self):
        """기기를 옮겨도 따라오게 하려면 계정이 먼저다"""
        user = self.make_user()
        user.list_paging = 'scroll'
        user.save()
        self.client.cookies['pd_paging'] = 'pages'
        self.client.force_login(user)
        self.assertTrue('id="scroll-sentinel"' in self.html(self.get()))

    def test_모르는_값은_거절한다(self):
        r = self.client.post(self.url, {'paging': 'drop table'})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('pd_paging', self.client.cookies)

    def test_GET_으로는_못_바꾼다(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class ButtonClassTest(BaseTest):
    """규칙 7 - 넘기기 버튼이 밀도 버튼 클래스를 쓰면 안 된다

    base.html 의 밀도 핸들러는 `.density-btn` 을 전부 집어간다. 넘기기 버튼에
    그 클래스를 같이 붙이면 핸들러가 먼저 'on' 을 달아주고, 넘기기 핸들러는
    '이미 켜져 있다'며 그냥 돌아간다. 버튼이 눌려도 아무 일이 안 일어난다.
    2026-11-22 에 실제로 이렇게 만들었다가 바로 잡았다.
    """

    def _tpl(self):
        with open(TPL, encoding='utf-8') as f:
            return f.read()

    def test_넘기기_버튼에_density_btn_이_없다(self):
        for m in re.finditer(r'<button[^>]*class="([^"]*)"[^>]*>', self._tpl()):
            cls = m.group(1)
            if 'paging-btn' in cls:
                self.assertTrue('density-btn' not in cls,
                                '넘기기 버튼에 density-btn 이 붙어 있다: %r' % cls)

    def test_넘기기_버튼이_실제로_두_개_있다(self):
        """위 검사가 허수가 되지 않게 버튼이 있는지도 본다"""
        self.assertEqual(self._tpl().count('class="paging-btn'), 2)

    def test_모양은_같게_유지한다(self):
        """클래스를 떼어냈으니 CSS 에 나란히 적어줘야 생김새가 안 깨진다"""
        tpl = self._tpl()
        self.assertTrue(re.search(r'\.density-btn,\s*\n\s*\.paging-btn\s*\{', tpl),
                        '.paging-btn 기본 모양 규칙이 없다')
        self.assertTrue(re.search(r'\.density-btn\.on,\s*\n\s*\.paging-btn\.on\s*\{', tpl),
                        '.paging-btn.on 규칙이 없다')


class ScrollGuardTest(BaseTest):
    """규칙 6 - 쪽수 보기에서는 무한 스크롤 코드가 아예 안 돈다"""

    def test_무한_스크롤이_모드를_먼저_본다(self):
        with open(TPL, encoding='utf-8') as f:
            tpl = f.read()
        i = tpl.find('// 무한 스크롤 + 스크롤 복원')
        self.assertNotEqual(i, -1, '무한 스크롤 블록을 못 찾았다')
        head = tpl[i:i + 400]
        self.assertTrue("list_paging" in head and "!== 'scroll'" in head and 'return' in head,
                        '무한 스크롤이 모드를 확인하지 않고 바로 켜진다')
