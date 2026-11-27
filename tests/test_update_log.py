"""업데이트 내역 - 달 버튼으로 끊어 보기

예전에는 41줄 2,700자가 한 덩어리로 쏟아져서 읽을 수가 없었다.
달 버튼을 누르면 그 달만 보이게 바꿨다 (2026-11-27).

여기서 지키는 것은 세 가지다.
  1. 적은 줄이 하나도 사라지지 않는다 - 날짜를 못 읽은 줄까지 포함해서.
  2. 최신이 앞에 온다.
  3. 「고침」 판정이 새 기능을 끌고 오지 않는다.
"""
from apps.core.models import SiteNotice

from .base import BaseTest


def notice(log):
    # location 이 unique 라 한 테스트에서 두 번 부르면 터진다.
    obj, _ = SiteNotice.objects.update_or_create(
        location='coordinates_list',
        defaults={'content': '내용', 'update_log': log})
    return obj


class GroupingTest(BaseTest):
    LOG = '\n'.join([
        '*가장 오래된 것 (26.01.10)',
        '*1월 두 번째 (26.01.19)',
        '*2월 것 (26.02.03)',
        '*같은 날 또 (26.02.03)',
        '*11월 것 (26.11.25)',
    ])

    def setUp(self):
        super().setUp()
        self.groups = notice(self.LOG).update_groups()

    def test_달로_묶인다(self):
        self.assertEqual([g['label'] for g in self.groups], ['11월', '2월', '1월'])

    def test_최신이_앞이다(self):
        first = self.groups[0]
        self.assertEqual(first['days'][0]['label'], '11월 25일')
        self.assertEqual(first['days'][0]['items'][0]['text'], '11월 것')

    def test_같은_날은_한_덩어리다(self):
        feb = self.groups[1]
        self.assertEqual(len(feb['days']), 1)
        self.assertEqual(len(feb['days'][0]['items']), 2)

    def test_날짜도_최신이_앞이다(self):
        jan = self.groups[2]
        self.assertEqual([d['label'] for d in jan['days']], ['1월 19일', '1월 10일'])

    def test_연도를_들고_있다(self):
        self.assertEqual(self.groups[0]['year'], '2026')

    def test_버튼마다_다른_이름표를_쓴다(self):
        """같은 id 가 두 개면 버튼을 눌러도 엉뚱한 칸이 열린다."""
        keys = [g['key'] for g in self.groups]
        self.assertEqual(len(keys), len(set(keys)))


class NothingLostTest(BaseTest):
    def test_줄_수가_그대로다(self):
        log = '\n'.join('*내용%d (26.%02d.%02d)' % (i, i % 12 + 1, i % 28 + 1)
                        for i in range(40))
        groups = notice(log).update_groups()
        total = sum(len(d['items']) for g in groups for d in g['days'])
        self.assertEqual(total, 40)

    def test_날짜를_못_읽은_줄도_살아남는다(self):
        """관리자가 형식을 어긋나게 적었다고 공지가 조용히 사라지면
        아무도 알아차리지 못한다. 맨 뒤 「기타」로 모은다."""
        groups = notice('*멀쩡한 줄 (26.11.25)\n날짜가 없는 줄\n*괄호도 없음').update_groups()
        last = groups[-1]
        self.assertEqual(last['label'], '기타')
        texts = [it['text'] for it in last['days'][0]['items']]
        self.assertIn('날짜가 없는 줄', texts)
        self.assertIn('괄호도 없음', texts)

    def test_빈_줄은_버린다(self):
        groups = notice('*하나 (26.11.25)\n\n\n*둘 (26.11.25)').update_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['days'][0]['items']), 2)

    def test_내역이_없으면_빈_목록이다(self):
        self.assertEqual(notice('').update_groups(), [])


class FixTagTest(BaseTest):
    def _fix(self, text):
        g = notice('*%s (26.11.25)' % text).update_groups()
        return g[0]['days'][0]['items'][0]['fix']

    def test_고친_것은_고침이다(self):
        self.assertTrue(self._fix('PC에서 지도가 안 보이던 문제 수정'))
        self.assertTrue(self._fix('표시가 사라지던 문제를 고쳤습니다'))

    def test_수정이라는_글자만으로는_안_된다(self):
        """「글 수정 시에도 ... 버튼 추가」는 새 기능이다.
        '수정' 하나를 보고 갈랐더니 이게 고침으로 끌려왔다."""
        self.assertFalse(self._fix('글 수정 시에도 내 위치 입력하기 버튼 추가'))

    def test_나머지는_새_기능이다(self):
        self.assertFalse(self._fix('피크민 자랑 게시판 추가'))


class ScreenTest(BaseTest):
    """실제 화면에 버튼과 칸이 나오는가"""

    def setUp(self):
        super().setUp()
        notice('*열한월 (26.11.25)\n*시월 (26.10.01)')
        self.make_coord()
        self.html = self.client.get('/coordinates/').content.decode()

    def test_달_버튼이_나온다(self):
        self.assertEqual(self.html.count('data-up="'), 2)

    def test_버튼과_담는_칸의_이름이_갈라져_있다(self):
        """담는 칸을 up-chips 로 뒀더니 버튼(up-chip)을 셀 때 같이 세어졌다.
        눈으로 찾을 때도 똑같이 헷갈린다."""
        self.assertIn('class="up-tabs"', self.html)
        self.assertNotIn('up-chips', self.html)

    def test_첫_칸만_열려_있다(self):
        """다 열려 있으면 예전과 똑같이 쏟아진다."""
        self.assertEqual(self.html.count('up-panel on'), 1)
        self.assertEqual(self.html.count('up-chip on'), 1)

    def test_버튼과_칸의_이름표가_맞는다(self):
        """data-up 이 가리키는 id 가 실제로 있어야 버튼이 먹는다."""
        import re
        keys = re.findall(r'data-up="([^"]+)"', self.html)
        ids = re.findall(r'class="up-panel[^"]*" id="([^"]+)"', self.html)
        self.assertTrue(keys)
        self.assertEqual(sorted(keys), sorted(ids))

    def test_옛_방식으로는_안_그린다(self):
        """linebreaks 로 통째로 뿌리던 자리가 남아 있으면 두 번 나온다."""
        with open('templates/coordinates/list.html', encoding='utf-8') as f:
            self.assertNotIn('update_log|linebreaks', f.read())
