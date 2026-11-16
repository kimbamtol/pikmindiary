"""피크민 표식과 복사 효과

지켜야 할 규칙은 네 가지다.

1. 아무것도 안 고른 사람도 피크민이 있어야 한다. 비어 보이면 안 된다.
2. 머리와 마릿수는 고를 수 없다. 받은 복사 수만이 정한다.
3. 복사하면 글쓴이의 copy_total 이 올라야 한다. 안 오르면 머리가 영영 안 핀다.
4. 전용 탈것은 허락받은 사람만 쓴다. POST 로 밀어넣어도 안 먹혀야 한다.
"""
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
