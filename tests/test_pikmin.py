"""피크민 표식과 복사 효과

지켜야 할 규칙은 여섯 가지다.

1. 아무것도 안 고른 사람도 피크민이 있어야 한다. 비어 보이면 안 된다.
2. 머리와 마릿수는 고를 수 없다. 받은 복사 수만이 정한다.
3. 복사하면 글쓴이의 copy_total 이 올라야 한다. 안 오르면 머리가 영영 안 핀다.
4. 전용 탈것은 허락받은 사람만 쓴다. POST 로 밀어넣어도 안 먹혀야 한다.
5. 걷기 진폭에 상한이 있다. 넘으면 파츠가 따로 노는 것처럼 보인다.
6. 「꽃 색」칸에는 꽃이 보여야 한다. 고르는 게 뭔지 그림으로 알 수 있어야 한다.
7. 피크민이 쓰는 클래스 이름을 **다른 스타일시트가 홑 선택자로 잡으면 안 된다.**
   이름만 보고 잡는 규칙은 남의 그림에 올라탄다.
8. 복사 효과는 카드가 감당할 만큼만 내보내고, 마지막 한 마리가 도착한 뒤에 치운다.
9. **fetch 로 붙인 조각에도 표식을 그려야 한다.** pikmin.js 는 혼자 깨어나지 않는다.
"""
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.coordinates.models import Coordinate
from apps.interactions.models import Notification

from .base import BaseTest

User = get_user_model()


class AutoAssignTest(BaseTest):
    """1. 안 고른 사람도 비어 보이지 않는다"""

    def test_색과_꽃이_비어도_값이_나온다(self):
        u = self.make_user()
        self.assertEqual(u.pikmin_color, '')
        self.assertEqual(u.pikmin_flower, '')
        self.assertIn(u.pikmin_color_key, dict(u.PIKMIN_COLORS))
        self.assertIn(u.pikmin_flower_key, dict(u.PIKMIN_FLOWERS))

    def test_같은_사람은_언제나_같은_색이_나온다(self):
        u = self.make_user()
        first = (u.pikmin_color_key, u.pikmin_flower_key, u.pikmin_sub_key)
        again = User.objects.get(pk=u.pk)
        self.assertEqual(first, (again.pikmin_color_key, again.pikmin_flower_key,
                                 again.pikmin_sub_key))

    def test_고른_값이_자동값을_이긴다(self):
        u = self.make_user()
        u.pikmin_color = 'purple'
        u.pikmin_flower = 'blue'
        self.assertEqual(u.pikmin_color_key, 'purple')
        self.assertEqual(u.pikmin_flower_key, 'blue')

    def test_잎_번호는_꽃_색을_따라간다(self):
        u = self.make_user()
        u.pikmin_flower = 'red'
        self.assertEqual(u.pikmin_leaf_key, 3)   # PIKMIN_FLOWERS 에서 red 는 4번째


class TierTest(BaseTest):
    """2. 머리와 마릿수는 받은 복사 수만이 정한다"""

    def test_복사_수에_따라_머리가_바뀐다(self):
        u = self.make_user()
        for total, tier in [(0, 'leaf'), (999, 'leaf'), (1000, 'bud'),
                            (9999, 'bud'), (10000, 'flower'), (90000, 'flower')]:
            u.copy_total = total
            self.assertEqual(u.pikmin_tier, tier, '복사 %d회' % total)

    def test_마릿수는_천_복사에_하나씩_최대_열둘(self):
        u = self.make_user()
        for total, herd in [(0, 1), (999, 1), (1000, 2), (5500, 6), (11000, 12), (90000, 12)]:
            u.copy_total = total
            self.assertEqual(u.pikmin_herd, herd, '복사 %d회' % total)

    def test_설정_화면에서_머리를_못_고른다(self):
        """POST 로 밀어넣어도 머리와 마릿수는 안 바뀐다"""
        u = self.login()
        self.client.post(reverse('accounts:my_settings'), {
            'nickname': u.nickname, 'bio': '',
            'pikmin_color': 'blue',
            'pikmin_tier': 'flower', 'copy_total': '99999', 'pikmin_herd': '12',
        })
        u.refresh_from_db()
        self.assertEqual(u.pikmin_color, 'blue')     # 색은 바뀌고
        self.assertEqual(u.copy_total, 0)            # 복사 수는 안 바뀐다
        self.assertEqual(u.pikmin_tier, 'leaf')

    def test_다음_단계까지_남은_수를_알려준다(self):
        u = self.make_user()
        u.copy_total = 300
        self.assertEqual(u.pikmin_next_tier(), ('bud', 700))
        u.copy_total = 1200
        self.assertEqual(u.pikmin_next_tier(), ('flower', 8800))
        u.copy_total = 10000
        self.assertIsNone(u.pikmin_next_tier())


class CopyTotalTest(BaseTest):
    """3. 복사하면 합계가 오른다"""

    def test_복사하면_글쓴이_합계가_오른다(self):
        author = self.make_user()
        coord = self.make_coord(author=author)
        self.client.get(reverse('coordinates:copy_coords', args=[coord.pk]))
        author.refresh_from_db()
        self.assertEqual(author.copy_total, 1)

    def test_비회원_글은_올릴_사람이_없어도_안_터진다(self):
        coord = self.make_coord(author=None)
        r = self.client.get(reverse('coordinates:copy_coords', args=[coord.pk]))
        self.assertEqual(r.status_code, 200)

    def test_천_번째_복사에서_봉오리_알림이_온다(self):
        author = self.make_user()
        author.copy_total = 999
        author.save(update_fields=['copy_total'])
        coord = self.make_coord(author=author)
        self.client.get(reverse('coordinates:copy_coords', args=[coord.pk]))
        msgs = Notification.objects.filter(
            recipient=author,
            notification_type=Notification.NotificationType.COPY_MILESTONE,
        ).values_list('message', flat=True)
        self.assertTrue(any('봉오리' in m for m in msgs), list(msgs))

    def test_글이_지워지면_합계에서_빠진다(self):
        author = self.login()
        coord = self.make_coord(author=author, copy_count=40)
        author.recount_copy_total()
        author.refresh_from_db()
        self.assertEqual(author.copy_total, 40)
        coord.delete()
        author.recount_copy_total()
        author.refresh_from_db()
        self.assertEqual(author.copy_total, 0)

    def test_승인_안_된_글은_합계에_안_들어간다(self):
        author = self.make_user()
        self.make_coord(author=author, copy_count=50, status=Coordinate.Status.PENDING)
        self.assertEqual(author.recount_copy_total(), 0)


class MountTest(BaseTest):
    """4. 전용 탈것은 허락받은 사람만"""

    def test_허락_없으면_저장해도_안_먹는다(self):
        u = self.make_user()
        u.pikmin_mount = 'turtle'
        self.assertEqual(u.get_available_mounts(), [])
        self.assertEqual(u.pikmin_mount_key, '')

    def test_허락받으면_탄다(self):
        u = self.make_user()
        u.exclusive_perks = 'turtle'
        u.pikmin_mount = 'turtle'
        self.assertEqual(u.get_available_mounts(), ['turtle'])
        self.assertEqual(u.pikmin_mount_key, 'turtle')

    def test_설정_화면으로_몰래_못_켠다(self):
        u = self.login()
        self.client.post(reverse('accounts:my_settings'), {
            'nickname': u.nickname, 'bio': '', 'pikmin_mount': 'turtle',
        })
        u.refresh_from_db()
        self.assertEqual(u.pikmin_mount, '')
        self.assertEqual(u.pikmin_mount_key, '')

    def test_모르는_코드는_안_받는다(self):
        u = self.make_user()
        u.exclusive_perks = 'dragon'
        u.pikmin_mount = 'dragon'
        self.assertEqual(u.pikmin_mount_key, '')


class MarkRenderTest(BaseTest):
    """화면에 실제로 나오나"""

    def test_기본은_이름_옆에_안_나온다(self):
        """아무도 안 물어보고 켜면 안 된다. 기본은 꺼짐이다."""
        author = self.make_user()
        self.assertFalse(author.pikmin_show_mark)
        self.make_coord(author=author)
        body = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('data-pk-show="0"', body)
        self.assertIn('pk-hidden', body)

    def test_켜면_나온다(self):
        author = self.make_user()
        author.copy_total = 2500
        author.pikmin_show_mark = True
        author.save(update_fields=['copy_total', 'pikmin_show_mark'])
        self.make_coord(author=author)
        body = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('data-pk-show="1"', body)
        self.assertNotIn('pk-hidden', body)
        self.assertIn('data-pk-t="bud"', body)
        self.assertIn('data-pk-h="3"', body)

    def test_꺼도_복사_효과용_값은_남는다(self):
        """표식을 꺼도 무리는 지나간다. 값까지 없애면 무리를 못 만든다."""
        author = self.make_user()
        author.copy_total = 5000
        author.save(update_fields=['copy_total'])
        self.make_coord(author=author)
        body = self.client.get(reverse('coordinates:list')).content.decode()
        self.assertIn('data-pk-h="6"', body)
        self.assertIn('data-pk-t="bud"', body)

    def test_설정에서_켜고_끌_수_있다(self):
        u = self.login()
        self.client.post(reverse('accounts:my_settings'),
                         {'nickname': u.nickname, 'bio': '', 'pikmin_show_mark': '1'})
        u.refresh_from_db()
        self.assertTrue(u.pikmin_show_mark)
        self.client.post(reverse('accounts:my_settings'),
                         {'nickname': u.nickname, 'bio': ''})
        u.refresh_from_db()
        self.assertFalse(u.pikmin_show_mark)

    def test_비회원_글에는_표식이_없다(self):
        self.make_coord(author=None)
        r = self.client.get(reverse('coordinates:list'))
        self.assertNotIn('pk-mark', r.content.decode())

    def test_설정_화면에_칩이_다_나온다(self):
        u = self.login()
        r = self.client.get(reverse('accounts:my_settings'))
        body = r.content.decode()
        self.assertEqual(body.count('name="pikmin_color"'), 8)
        self.assertEqual(body.count('name="pikmin_flower"'), 5)
        self.assertEqual(body.count('name="pikmin_mount"'), 0)   # 허락 없으면 안 보인다


class WalkAmplitudeTest(BaseTest):
    """5. 걷기 진폭 상한 — 2026-11-18 (건의 #29)

    **먼저 밝혀둔다. 이 상한은 건의 #29 의 답이 아니다.** 진짜 원인은 seasons.css
    의 `.leaf` 였고 ClassNameCollisionTest 가 지킨다. 진폭을 줄인 것은 번지는
    속도만 늦춘 오진이었다. 상한 자체는 그대로 쓸모가 있어서 남겨둔다.

    당시 기록: 애니메이션이 어긋나는 게 아니었다 — 5분 + 스크롤 왕복 뒤에도
    한 마리 안의 여섯 파트 위상은 소수점 네 자리까지 같았다.

    한 걸음(0.74초)마다 머리가 제 너비(8.4)의 48% 인 4.0 을 움직였고, 몸통은
    제 너비(13.8)의 20% 인 2.8 만큼 발에서 어긋났다. 다리는 bod 바깥에 있어서
    (발은 땅에 남겨야 한다) 몸이 미끄러져도 안 따라오기 때문이다.

    이름 옆 표식은 19px 이라 티가 안 났지만, 설정 화면의 큰 미리보기는 44px —
    2.3배다. 그리고 거기가 피크민을 크게, 오래 보는 유일한 화면이다.

    키프레임 숫자는 viewBox 유닛이라 **크기와 무관한 설계값**이다. 여기를 다시
    올리면 모든 화면에서 같이 커진다.
    """

    CSS = None

    def _css(self):
        if WalkAmplitudeTest.CSS is None:
            path = settings.BASE_DIR / 'static' / 'css' / 'pikmin.css'
            WalkAmplitudeTest.CSS = path.read_text(encoding='utf-8')
        return WalkAmplitudeTest.CSS

    def _frames(self, name):
        """@keyframes <name>{...} 안의 본문을 꺼낸다.

        안에 또 중괄호가 있어서(0%{...}) 정규식만으로는 끝을 못 찾는다.
        여는 괄호부터 세면서 짝이 맞는 자리까지 잘라낸다.
        """
        css = self._css()
        m = re.search(r'@keyframes\s+' + name + r'\s*\{', css)
        self.assertIsNotNone(m, '@keyframes %s 를 못 찾았다' % name)
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += {'{': 1, '}': -1}.get(css[i], 0)
            i += 1
        self.assertEqual(depth, 0, '@keyframes %s 의 끝을 못 찾았다' % name)
        return css[m.end():i - 1]

    def _max(self, body, func):
        vals = [abs(float(v)) for v in
                re.findall(r'%s\(\s*(-?[\d.]+)' % func, body)]
        self.assertTrue(vals, '%s() 가 하나도 없다' % func)
        return max(vals)

    def test_머리_흔들림은_8도를_넘지_않는다(self):
        """13도였다. 13도면 머리가 제 너비의 절반을 움직인다."""
        deg = self._max(self._frames('sway'), 'rotate')
        self.assertLessEqual(deg, 8, '잎·꽃이 %.1f도 흔들린다' % deg)

    def test_몸통_흔들림은_2_5도를_넘지_않는다(self):
        deg = self._max(self._frames('waddle'), 'rotate')
        self.assertLessEqual(deg, 2.5, '몸통이 %.1f도 흔들린다' % deg)

    def test_몸통_좌우_미끄러짐은_0_5를_넘지_않는다(self):
        """다리가 안 따라오는 양이다. 여기가 커지면 몸과 다리가 떨어져 보인다."""
        px = self._max(self._frames('waddle'), 'translateX')
        self.assertLessEqual(px, 0.5, '몸통이 %.2f 미끄러진다' % px)

    def test_걸음_박자는_그대로다(self):
        """진폭만 줄였다. 박자까지 건드리면 걷는 느낌이 사라진다."""
        self.assertIn('--P:.74s', self._css())

    def test_다리와_몸_끄덕임은_그대로다(self):
        """step 과 bob 은 '걷는다' 는 신호다. 줄이면 미끄러지는 것처럼 보인다."""
        self.assertGreaterEqual(self._max(self._frames('step'), 'rotate'), 10)
        self.assertGreaterEqual(self._max(self._frames('bob'), 'translateY'), 2.5)


class FlowerChipTest(BaseTest):
    """6. 「꽃 색」칸에 꽃이 보인다 — 2026-11-18 (건의 #29)

    "마이페이지에서 머리 위 꽃도 안 보이는것 같아요" 라는 제보를 받았다.
    제보한 분은 받은 복사 8회라 머리가 잎인 게 맞다. 그런데 칩까지 본인 단계로
    그려서, 분홍꽃·흰꽃·노란꽃 라벨 아래에 초록 잎만 다섯 개 있었다.
    게다가 그분이 고른 분홍꽃은 자동 배정값과 같아서 눌러도 아무것도 안 바뀌었다.

    칩은 단계와 상관없이 늘 꽃으로 그린다. 미리보기는 실제 단계 그대로 둔다 —
    거기까지 꽃으로 그리면 아직 안 핀 꽃을 폈다고 거짓말하는 셈이다.
    """

    def _chips(self, body):
        m = re.search(r'id="pk-flowers"(.*?)</div>', body, re.S)
        self.assertIsNotNone(m, '꽃 색 칸을 못 찾았다')
        return m.group(1)

    def test_잎_단계여도_칩은_꽃으로_그린다(self):
        u = self.login()
        self.assertEqual(u.pikmin_tier, 'leaf')
        chips = self._chips(self.client.get(reverse('accounts:my_settings')).content.decode())
        self.assertEqual(chips.count('data-pk-t="flower"'), 5,
                         '「꽃 색」칸에 꽃이 다섯 개가 아니다')
        self.assertNotIn('data-pk-t="leaf"', chips)

    def test_미리보기는_실제_단계_그대로다(self):
        """칩은 꽃이어도 본인 머리는 사실대로 보여준다"""
        self.login()
        body = self.client.get(reverse('accounts:my_settings')).content.decode()
        m = re.search(r'id="pk-preview"(.*?)></span>', body, re.S)
        self.assertIsNotNone(m)
        self.assertIn('data-pk-t="leaf"', m.group(1))

    def test_꽃이_핀_사람도_칩은_그대로_다섯_개다(self):
        u = self.login()
        u.copy_total = 20000
        u.save(update_fields=['copy_total'])
        body = self.client.get(reverse('accounts:my_settings')).content.decode()
        self.assertEqual(self._chips(body).count('data-pk-t="flower"'), 5)
        m = re.search(r'id="pk-preview"(.*?)></span>', body, re.S)
        self.assertIn('data-pk-t="flower"', m.group(1))

    def test_도움말이_칩보다_위에_있다(self):
        """아래에 두면 칩을 다 눌러본 뒤에야 읽는다"""
        self.login()
        body = self.client.get(reverse('accounts:my_settings')).content.decode()
        self.assertIn('pk-help-top', body)
        self.assertLess(body.index('pk-help-top'), body.index('id="pk-flowers"'))

    def test_잎_단계에는_언제_피는지_알려준다(self):
        self.login()
        body = self.client.get(reverse('accounts:my_settings')).content.decode()
        self.assertIn('1,000', body)
        self.assertIn('봉오리', body)


class ClassNameCollisionTest(BaseTest):
    """7. 피크민 클래스 이름을 남이 홑 선택자로 잡으면 안 된다 — 2026-11-18

    건의 #29 의 진짜 원인이다. seasons.css 의 가을 낙엽 효과가 이랬다.

        .leaf { position:absolute; animation: leaffall linear infinite }

    피크민은 머리 위 잎을 class="leaf lf1" 로 그린다. 그래서 표식의 잎이
    낙엽이 되어 translateY(100vh) 로 떠내려가고 opacity 0 으로 사라졌다.

    거기서 끝이 아니다. .stem 과 .tilt 는 transform-box:fill-box 라 바깥 상자가
    자식을 따라 커진다. 떠내려간 잎이 상자를 10.7 에서 167.3 까지 끌고 갔고,
    transform-origin:bottom center 가 그만큼 아래로 내려갔다. sway 와 waddle 이
    저 멀리 있는 점을 축으로 돌면서 몸통이 좌우로 춤췄다. 27px 짜리 표식 안에서
    몸통 그룹이 8.5초 만에 385px 까지 자랐다.

    피크민은 body·face·shadow·arm·stem 처럼 흔한 이름을 쓴다. 지금은 .leaf
    하나만 겹쳤지만 누가 `.shadow {}` 를 쓰면 똑같이 터진다. 그래서 이름 하나가
    아니라 **규칙**을 지킨다.
    """

    #: pikmin.js 가 만들지만 class="..." 안에는 안 보이는 것들
    EXTRA = {'walk', 'fly', 'go', 'pk-mark', 'pk-runners', 'pk-on',
             'pk-big', 'pk-hidden', 'pk-chip-art'}

    def _names(self):
        """pikmin.js 가 실제로 붙이는 클래스 이름을 긁어온다.

        손으로 적어두면 새 파츠를 넣을 때 아무도 안 고친다.
        """
        js = (settings.BASE_DIR / 'static' / 'js' / 'pikmin.js').read_text(encoding='utf-8')
        names = set()
        for m in re.finditer(r'class="([^"]*)"', js):
            # ${...} 는 색·등급처럼 값이 들어가는 자리다
            for tok in re.sub(r'\$\{[^}]*\}', ' ', m.group(1)).split():
                if re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', tok):
                    names.add(tok)
        return names | self.EXTRA

    def _selectors(self, css):
        """여는 중괄호 앞에 오는 선택자 목록만 뽑는다"""
        css = re.sub(r'/\*.*?\*/', ' ', css, flags=re.S)
        out = []
        for m in re.finditer(r'(?:^|[}])([^{}]*)\{', css, flags=re.S):
            head = m.group(1).strip()
            if not head or head.startswith('@'):
                continue
            out.extend(p.strip() for p in head.split(','))
        return [p for p in out if p]

    def test_피크민_이름을_긁어온다(self):
        """이 테스트가 헛돌고 있지 않은지부터 본다"""
        names = self._names()
        for must in ('leaf', 'stem', 'tilt', 'bod', 'shadow', 'body', 'face'):
            self.assertIn(must, names, '%s 를 못 긁었다 - 긁는 방식이 깨졌다' % must)

    def test_다른_스타일시트가_홑_선택자로_안_잡는다(self):
        names = self._names()
        css_dir = settings.BASE_DIR / 'static' / 'css'
        bad = []
        for path in sorted(css_dir.glob('*.css')):
            if path.name == 'pikmin.css':
                continue            # 제 그림은 제가 잡아도 된다
            for sel in self._selectors(path.read_text(encoding='utf-8')):
                if sel.startswith('.') and sel[1:] in names:
                    bad.append('%s 의 `%s`' % (path.name, sel))
        self.assertEqual(
            bad, [],
            '피크민 클래스 이름을 홑 선택자로 잡는 규칙이 있다. '
            '`.leaves .leaf` 처럼 제 자리 안으로 한정해라: ' + ', '.join(bad))

    def test_낙엽은_제_자리_안에서만_떨어진다(self):
        css = (settings.BASE_DIR / 'static' / 'css' / 'seasons.css').read_text(encoding='utf-8')
        self.assertTrue('.leaves .leaf' in css,
                        '낙엽 규칙이 .leaves 안으로 한정돼 있어야 한다')
        for sel in self._selectors(css):
            self.assertFalse(
                sel == '.leaf' or sel.startswith('.leaf:'),
                '`%s` 가 남아 있다. 피크민 머리의 잎까지 떨어뜨린다' % sel)


class ParadeTest(BaseTest):
    """8. 복사 효과 — 2026-11-18

    두 가지를 쟀다.

    하나. 218px 짜리 폰 카드에 12마리를 내보내면 이웃 간격이 23px 이 된다.
    한 마리 폭이 24px 이라 줄지어 가는 게 아니라 겹친 벽이 되어 지나간다.
    승인된 글 2,607개 중 74.1% 가 9마리 이상인 작성자의 글이다.

    둘. 상자를 1900ms 에 통째로 비웠는데 마지막 주자는 935ms 늦게 떠나
    2435ms 에 끝난다. 카드 한복판에서 투명도 1인 채로 여덟 마리가 한꺼번에
    사라졌다. 걸어 나가는 게 아니라 끊겼다.
    """

    def _js(self):
        return (settings.BASE_DIR / 'static' / 'js' / 'pikmin.js').read_text(encoding='utf-8')

    def _code(self):
        """주석을 뺀 알맹이. 옛 숫자는 주석에 사연으로 남아 있다"""
        js = re.sub(r'/\*.*?\*/', ' ', self._js(), flags=re.S)
        return re.sub(r'//[^\n]*', ' ', js)

    def _has(self, pattern):
        """통째로 쏟아내지 않는다. 실패 메시지는 짧아야 읽는다"""
        return re.search(pattern, self._code()) is not None

    def test_치우는_시각을_박아두지_않는다(self):
        self.assertNotIn('1900', self._code(),
                         '치우는 시각을 숫자로 박아두면 마릿수가 바뀔 때 또 끊긴다')
        self.assertTrue(
            self._has(r'setTimeout\([\s\S]*?DASH \+ GAP \* \(n - 1\)'),
            '마지막 주자가 도착한 뒤에 치워야 한다 '
            '(setTimeout 의 시각이 DASH + GAP * (n - 1) 이어야 한다)')

    def test_마릿수를_카드_폭에_맞춘다(self):
        self.assertTrue(
            self._has(r'Math\.min\(k\.h, Math\.round\(wide / 36\)\)'),
            '카드가 감당할 만큼만 내보내야 한다')
        self.assertTrue(
            self._has(r'for \(let i = 0; i < n; i\+\+\)'),
            '무리 전체(k.h)가 아니라 추린 수(n)만큼 돌아야 한다')

    def test_박자_값은_CSS_와_같다(self):
        """JS 의 DASH·GAP 이 CSS 의 dash 길이와 어긋나면 또 끊긴다"""
        js = self._js()
        css = (settings.BASE_DIR / 'static' / 'css' / 'pikmin.css').read_text(encoding='utf-8')
        m = re.search(r'animation:\s*dash\s+([\d.]+)s', css)
        self.assertIsNotNone(m, 'CSS 에서 dash 길이를 못 찾았다')
        self.assertIn('const DASH = %s;' % m.group(1), js,
                      'JS 의 DASH 가 CSS 의 dash 길이와 달라졌다')


class FragmentDrawTest(BaseTest):
    """9. fetch 로 붙인 조각에도 표식을 그려야 한다 — 2026-11-18

    pikmin.js 는 DOMContentLoaded 와 htmx:afterSettle/afterSwap 에만 깨어난다.
    그런데 목록 무한 스크롤(appendCards)과 댓글 모달은 HTMX 가 아니라 맨 fetch 다.
    그 행사가 안 열리니 새로 붙은 `.pk-mark` 는 빈 껍데기로 남는다.

    잰 값: 목록을 끝까지 내리면 표식 84개 중 그려진 것이 **12개**였다. 첫 쪽
    말고는 하나도 없었다. 댓글 모달은 켠 사람의 표식이 **0개** 그려졌다.

    `window.pikminDraw(root)` 를 붙이는 자리에서 직접 불러야 한다.
    """

    #: 표식이 들어 있는 조각 템플릿
    MARK_FRAGMENTS = ('coordinates/_card_list.html',
                      'comments/_comment_modal_content.html')

    def _tpl(self, rel):
        return (settings.BASE_DIR / 'templates' / rel).read_text(encoding='utf-8')

    def test_조각에_표식이_들어_있다(self):
        """전제부터 확인한다. 조각에 표식이 없으면 아래 테스트가 헛돈다"""
        for rel in self.MARK_FRAGMENTS:
            self.assertIn('pikmin_mark', self._tpl(rel),
                          '%s 에 표식이 없다 - 이 테스트의 전제가 깨졌다' % rel)

    def test_무한_스크롤이_붙인_카드를_그린다(self):
        js = self._tpl('coordinates/list.html')
        i = js.find('function appendCards')
        self.assertNotEqual(i, -1, 'appendCards 를 못 찾았다')
        body = js[i:i + 800]
        self.assertIn('pikminDraw', body,
                      '불러온 카드에 pikminDraw 를 안 부르면 첫 쪽 말고는 '
                      '표식이 전부 빈 껍데기로 남는다')

    def test_댓글을_가져오는_모든_곳이_그린다(self):
        """조각 주소를 부르는 자리를 전부 훑는다. 한 곳만 고치면 다른 곳이 남는다"""
        found = 0
        for path in sorted((settings.BASE_DIR / 'templates').rglob('*.html')):
            text = path.read_text(encoding='utf-8')
            for m in re.finditer(r"fetch\('/comments/list/", text):
                found += 1
                near = text[m.start():m.start() + 500]
                self.assertIn(
                    'pikminDraw', near,
                    '%s 의 %d번째 글자 근처: 댓글을 붙이고 pikminDraw 를 안 불렀다'
                    % (path.name, m.start()))
        self.assertGreaterEqual(found, 2,
                                '댓글을 가져오는 자리를 하나도 못 찾았다 - '
                                '찾는 방식이 깨졌다')
