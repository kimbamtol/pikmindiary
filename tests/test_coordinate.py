"""좌표 글 - 작성, 수정, 삭제, 권한

이 사이트의 본체다. 비회원이 닉네임+비밀번호로 쓰고 고치는 흐름이 특히 중요하다.
비밀번호는 해시로 저장되므로 '맞는 비밀번호는 통과, 틀린 비밀번호는 차단'을 둘 다 본다.
"""
from django.contrib.auth.hashers import check_password
from django.urls import reverse

from apps.core.models import SiteSettings
from apps.coordinates.models import Coordinate

from .base import BaseTest


class CreateTest(BaseTest):
    def post_data(self, **kw):
        data = {
            'title': '버섯 좌표',
            'postcard_name': '테스트 엽서',
            'description': '설명',
            'latitude': '35.123456',
            'longitude': '129.123456',
            'category': Coordinate.Category.MUSHROOM,
        }
        data.update(kw)
        return data

    def test_회원이_글을_쓴다(self):
        user = self.login(self.make_user(nickname='작성자'))
        res = self.client.post(reverse('coordinates:create'), self.post_data())

        self.assertEqual(res.status_code, 302)
        coord = Coordinate.objects.get(title='버섯 좌표')
        self.assertEqual(coord.author, user)
        self.assertEqual(coord.status, Coordinate.Status.APPROVED)
        self.assertEqual(res.url, reverse('coordinates:detail', args=[coord.pk]))

    def test_비회원이_닉네임과_비밀번호로_글을_쓴다(self):
        self.client.post(reverse('coordinates:create'), self.post_data(
            guest_nickname='지나가던사람', guest_password='비밀1234'))

        coord = Coordinate.objects.get(title='버섯 좌표')
        self.assertIsNone(coord.author)
        self.assertTrue(check_password('비밀1234', coord.guest_password))
        # 비밀번호가 평문으로 남으면 안 된다
        self.assertNotEqual(coord.guest_password, '비밀1234')

    def test_비회원이_닉네임_없이_쓰면_저장되지_않는다(self):
        res = self.client.post(reverse('coordinates:create'), self.post_data())
        self.assertEqual(res.status_code, 200)        # 폼으로 되돌아온다
        self.assertFalse(Coordinate.objects.filter(title='버섯 좌표').exists())

    def test_하루_업로드_한도를_넘기면_막힌다(self):
        s = SiteSettings.get_settings()
        s.daily_upload_limit = 2
        s.ranker_limit_exempt_rank = 0
        s.save()

        self.login(self.make_user())
        for i in range(2):
            self.client.post(reverse('coordinates:create'), self.post_data(title='글%d' % i))
        self.assertEqual(Coordinate.objects.count(), 2)

        res = self.client.post(reverse('coordinates:create'), self.post_data(title='세번째'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 2)

    def test_카테고리가_다르면_한도가_따로_센다(self):
        s = SiteSettings.get_settings()
        s.daily_upload_limit = 1
        s.ranker_limit_exempt_rank = 0
        s.save()

        self.login(self.make_user())
        self.client.post(reverse('coordinates:create'),
                         self.post_data(title='버섯', category=Coordinate.Category.MUSHROOM))
        self.client.post(reverse('coordinates:create'),
                         self.post_data(title='모종', category=Coordinate.Category.SEEDLING))
        self.assertEqual(Coordinate.objects.count(), 2)


class EditDeleteTest(BaseTest):
    def test_작성자는_수정할_수_있다(self):
        user = self.login(self.make_user())
        coord = self.make_coord(author=user, title='원래 제목')

        self.client.post(reverse('coordinates:edit', args=[coord.pk]), {
            'title': '고친 제목', 'description': '', 'postcard_name': '',
            'latitude': coord.latitude, 'longitude': coord.longitude,
            'category': coord.category,
        })
        coord.refresh_from_db()
        self.assertEqual(coord.title, '고친 제목')

    def test_남의_글은_수정할_수_없다(self):
        owner = self.make_user(nickname='주인')
        coord = self.make_coord(author=owner, title='원래 제목')
        self.login(self.make_user(nickname='남'))

        self.client.post(reverse('coordinates:edit', args=[coord.pk]), {
            'title': '가로챈 제목', 'description': '', 'postcard_name': '',
            'latitude': coord.latitude, 'longitude': coord.longitude,
            'category': coord.category,
        })
        coord.refresh_from_db()
        self.assertEqual(coord.title, '원래 제목')

    def test_비회원_글은_비밀번호가_맞아야_수정된다(self):
        from django.contrib.auth.hashers import make_password
        coord = self.make_coord(author=None, title='원래 제목',
                                guest_password=make_password('비밀1234'))
        payload = {
            'title': '고친 제목', 'description': '', 'postcard_name': '',
            'latitude': coord.latitude, 'longitude': coord.longitude,
            'category': coord.category,
        }

        # 틀린 비밀번호
        self.client.post(reverse('coordinates:edit', args=[coord.pk]),
                         dict(payload, password='틀린비번'))
        coord.refresh_from_db()
        self.assertEqual(coord.title, '원래 제목')

        # 맞는 비밀번호
        self.client.post(reverse('coordinates:edit', args=[coord.pk]),
                         dict(payload, password='비밀1234'))
        coord.refresh_from_db()
        self.assertEqual(coord.title, '고친 제목')

    def test_작성자는_삭제할_수_있다(self):
        user = self.login(self.make_user())
        coord = self.make_coord(author=user)
        self.client.post(reverse('coordinates:delete', args=[coord.pk]))
        self.assertFalse(Coordinate.objects.filter(pk=coord.pk).exists())

    def test_남의_글은_삭제할_수_없다(self):
        coord = self.make_coord(author=self.make_user(nickname='주인'))
        self.login(self.make_user(nickname='남'))
        self.client.post(reverse('coordinates:delete', args=[coord.pk]))
        self.assertTrue(Coordinate.objects.filter(pk=coord.pk).exists())
