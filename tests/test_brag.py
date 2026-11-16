"""피크민 자랑 게시판

주 단위로 묶이고 주마다 1등이 새로 뽑히는 구조라, 기준이 되는 '주의 시작'이
랭킹과 같은 규칙(월요일 시작)을 쓰는지가 핵심이다. 여기가 어긋나면
좌표 목록 옆 위젯이 엉뚱한 글을 1등으로 보여준다.
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.brag.models import BragLike, BragPost

from .base import BaseTest, make_image


class BragCreateTest(BaseTest):
    def test_회원이_자랑을_올린다(self):
        self.login(self.make_user(nickname='자랑러'))
        self.client.post(reverse('brag:create'), {
            'caption': '드디어 모은 제주 엽서', 'image': make_image('brag.jpg')})

        post = BragPost.objects.get()
        self.assertEqual(post.caption, '드디어 모은 제주 엽서')
        self.assertTrue(post.image.name)

    def test_비회원도_닉네임과_비밀번호로_올린다(self):
        self.client.post(reverse('brag:create'), {
            'caption': '비회원 자랑', 'image': make_image('brag.jpg'),
            'guest_nickname': '지나가던', 'guest_password': '비밀1234'})

        post = BragPost.objects.get()
        self.assertIsNone(post.author)
        self.assertNotEqual(post.guest_password, '비밀1234')

    def test_사진_없이는_올라가지_않는다(self):
        self.login(self.make_user())
        self.client.post(reverse('brag:create'), {'caption': '사진 없음'})
        self.assertEqual(BragPost.objects.count(), 0)


class BragLikeTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.login(self.make_user(nickname='자랑러'))
        self.client.post(reverse('brag:create'), {
            'caption': '자랑', 'image': make_image('brag.jpg')})
        self.post = BragPost.objects.get()
        self.client.logout()

    def test_좋아요를_눌렀다_취소한다(self):
        self.login(self.make_user(nickname='독자'))
        url = reverse('brag:like', args=[self.post.pk])

        self.client.post(url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.like_count, 1)
        self.assertEqual(BragLike.objects.count(), 1)

        self.client.post(url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.like_count, 0)
        self.assertEqual(BragLike.objects.count(), 0)

    def test_같은_사람이_두_번_세어지지_않는다(self):
        self.login(self.make_user(nickname='독자'))
        url = reverse('brag:like', args=[self.post.pk])
        for _ in range(4):             # 눌렀다 취소 두 번
            self.client.post(url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.like_count, 0)
        self.assertLessEqual(BragLike.objects.count(), 1)


class BragWeekTest(BaseTest):
    """주 단위 묶기와 주간 1등"""

    def make_post(self, caption, likes=0, days_ago=0):
        post = BragPost.objects.create(
            author=self.make_user(nickname=caption),
            caption=caption, image='brag/dummy.jpg', like_count=likes)
        if days_ago:
            when = timezone.now() - timedelta(days=days_ago)
            BragPost.objects.filter(pk=post.pk).update(created_at=when)
            post.refresh_from_db()
        return post

    def test_주의_시작은_랭킹과_같은_규칙을_쓴다(self):
        """자랑 게시판의 '이번 주'와 랭킹의 '주간'이 같은 월요일을 가리켜야 한다"""
        from apps.rankings.models import Ranking
        from apps.rankings.utils import get_period_start

        self.assertEqual(BragPost.week_start(),
                         get_period_start(Ranking.PeriodType.WEEKLY))
        self.assertEqual(BragPost.week_start().weekday(), 0)   # 월요일

    def test_좋아요가_없으면_가장_최근_글을_보여준다(self):
        newest = self.make_post('최근글')
        top = BragPost.current_top()
        self.assertEqual(top['post'].pk, newest.pk)
        self.assertEqual(top['label'], '새로 올라온 자랑')

    def test_이번주_1등은_좋아요가_제일_많은_글(self):
        self.make_post('적게', likes=1)
        winner = self.make_post('많이', likes=9)
        self.make_post('보통', likes=5)

        self.assertEqual(BragPost.current_top()['post'].pk, winner.pk)

    def test_지난주_글은_이번주_1등에_끼지_않는다(self):
        self.make_post('지난주대박', likes=99, days_ago=9)
        this_week = self.make_post('이번주', likes=1)

        self.assertEqual(BragPost.current_top()['post'].pk, this_week.pk)

    def test_목록이_주별로_묶여서_나온다(self):
        self.make_post('이번주글', likes=1)
        self.make_post('지난주글', likes=1, days_ago=9)

        html = self.client.get(reverse('brag:list')).content.decode()
        self.assertEqual(html.count('class="brag-week-range"'), 2)

    def test_자랑이_없어도_목록이_뜬다(self):
        self.assertEqual(self.client.get(reverse('brag:list')).status_code, 200)
        self.assertIsNone(BragPost.current_top()['post'])
