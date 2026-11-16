"""실제로 메일로 날아온 500들을 다시 못 나게 막는다.

2026-11-16에 5개월치 로그를 뒤져 찾은 것들이다.
- 글 등록 500 16번: 좌표칸에 숫자가 아닌 게 들어가면 detect_region 의 float() 가 터졌다
- 댓글 500 6번: Image.Lanczos 는 없는 이름이다 (LANCZOS). 1920px 넘는 사진이면 터졌다
- 댓글 삭제 500 1번: 같은 원인. 지워지긴 했는데 사용자는 500만 봤다
"""
from django.urls import reverse

from apps.comments.models import Comment
from apps.coordinates.models import Coordinate

from .base import BaseTest, make_image


class CoordinateCreateTest(BaseTest):
    """글 등록 — 좌표가 이상해도 500이 나면 안 된다"""

    def _post(self, **over):
        data = {
            'title': '테스트 좌표', 'postcard_name': '', 'description': '설명을 길게 썼다',
            'latitude': '35.123456', 'longitude': '129.123456',
            'category': Coordinate.Category.MUSHROOM,
            'guest_nickname': '지나가던피크민', 'guest_password': 'pw1234',
        }
        data.update(over)
        return self.client.post(reverse('coordinates:create'), data)

    def test_정상이면_등록된다(self):
        r = self._post()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Coordinate.objects.count(), 1)

    def test_좌표가_비면_500이_아니라_안내다(self):
        r = self._post(latitude='', longitude='')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 0)

    def test_좌표에_글자가_섞여도_안_터진다(self):
        r = self._post(latitude='35.1도', longitude='129.1도')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 0)

    def test_좌표_키가_아예_없어도_안_터진다(self):
        r = self.client.post(reverse('coordinates:create'), {
            'title': 'x', 'category': Coordinate.Category.MUSHROOM,
            'guest_nickname': 'ㄱ', 'guest_password': 'p',
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 0)

    def test_범위를_벗어난_좌표는_막는다(self):
        self.assertEqual(self._post(latitude='999').status_code, 200)
        self.assertEqual(self._post(longitude='-500').status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 0)

    def test_제목이_비면_막는다(self):
        r = self._post(title='   ')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 0)

    def test_되돌아온_폼에_쓴_내용이_남아_있다(self):
        """긴 설명을 다시 쓰게 하면 안 된다"""
        r = self._post(latitude='엉터리', description='여기 벚꽃 엄청 예뻐요')
        self.assertContains(r, '여기 벚꽃 엄청 예뻐요')
        self.assertContains(r, '테스트 좌표')

    def test_좌표가_이상해도_지역은_기타로_간다(self):
        c = Coordinate(title='x', latitude='', longitude='', category='MUSHROOM')
        self.assertEqual(c.detect_region(), Coordinate.Region.OTHER)


class CommentPhotoTest(BaseTest):
    """댓글 사진 — 커도 터지면 안 된다"""

    def _big(self):
        return make_image('big.jpg', size=(2400, 3200))

    def test_큰_사진을_붙여도_등록된다(self):
        coord = self.make_coord(author=self.make_user())
        r = self.client.post(reverse('comments:create', args=[coord.pk]), {
            'content': '큰 사진 붙임', 'photo': self._big(),
            'guest_nickname': '비회원', 'guest_password': 'pw1234',
        })
        self.assertIn(r.status_code, (200, 302))
        self.assertEqual(Comment.objects.count(), 1)

    def test_큰_사진은_1920_안으로_줄어든다(self):
        from PIL import Image
        coord = self.make_coord(author=self.make_user())
        self.client.post(reverse('comments:create', args=[coord.pk]), {
            'content': 'x', 'photo': self._big(),
            'guest_nickname': '비회원', 'guest_password': 'pw1234',
        })
        c = Comment.objects.get()
        w, h = Image.open(c.photo.path).size
        self.assertLessEqual(max(w, h), 1920)

    def test_사진_파일이_사라져도_저장은_된다(self):
        """축소가 실패해도 댓글은 살아야 한다"""
        import os
        coord = self.make_coord(author=self.make_user())
        self.client.post(reverse('comments:create', args=[coord.pk]), {
            'content': 'x', 'photo': self._big(),
            'guest_nickname': '비회원', 'guest_password': 'pw1234',
        })
        c = Comment.objects.get()
        os.remove(c.photo.path)
        c.content = '고침'
        c.save()                      # 여기서 터지면 안 된다
        c.refresh_from_db()
        self.assertEqual(c.content, '고침')

    def test_큰_사진_댓글을_지울_수_있다(self):
        coord = self.make_coord(author=self.make_user())
        user = self.login()
        self.client.post(reverse('comments:create', args=[coord.pk]),
                         {'content': 'x', 'photo': self._big()})
        c = Comment.objects.get()
        r = self.client.post(reverse('comments:delete', args=[c.pk]))
        self.assertIn(r.status_code, (200, 302))
        c.refresh_from_db()
        self.assertTrue(c.is_deleted)
