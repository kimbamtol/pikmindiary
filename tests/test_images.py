"""업로드 사진 — 용량·형식 검사, HEIC 변환, 눕힌 사진 세우기.

2026-11-16에 셋을 한꺼번에 넣었다.
1. 좌표 업로드에 검사가 아예 없었다 (댓글만 있었다)
2. 아이폰 HEIC 를 서버가 못 열어서 깨진 채로 저장됐다
3. 세워 찍은 폰 사진이 눕혀서 올라갔다
"""
import io
import os

from PIL import Image
from django.urls import reverse

from apps.comments.models import Comment
from apps.coordinates.models import Coordinate, CoordinateImage

from .base import (BaseTest, make_heic, make_image, make_junk,
                   make_oversized, make_rotated_image)


class PrepareUploadTest(BaseTest):
    """공용 모듈 자체"""

    def _prep(self, f, **kw):
        from apps.core.images import prepare_upload
        return prepare_upload(f, **kw)

    def test_멀쩡한_사진은_그대로_둔다(self):
        """손댈 게 없으면 다시 압축하지 않는다 — 화질만 깎인다"""
        f = make_image('ok.jpg')
        out, err = self._prep(f)
        self.assertIsNone(err)
        self.assertIs(out, f)

    def test_이미지가_아니면_막는다(self):
        out, err = self._prep(make_junk())
        self.assertIsNone(out)
        self.assertIn('이미지', err)

    def test_용량이_넘으면_막는다(self):
        out, err = self._prep(make_oversized())
        self.assertIsNone(out)
        self.assertIn('MB', err)

    def test_heic는_jpeg로_바뀐다(self):
        out, err = self._prep(make_heic())
        self.assertIsNone(err)
        self.assertTrue(out.name.endswith('.jpg'), out.name)
        self.assertEqual(Image.open(out).format, 'JPEG')

    def test_눕힌_사진이_세워진다(self):
        """가로 400x200 + 회전값 6 -> 세로 200x400 이 되어야 한다"""
        out, err = self._prep(make_rotated_image())
        self.assertIsNone(err)
        self.assertEqual(Image.open(out).size, (200, 400))

    def test_세운_뒤에는_회전값이_남지_않는다(self):
        out, _err = self._prep(make_rotated_image())
        self.assertEqual(Image.open(out).getexif().get(0x0112, 1), 1)

    def test_너무_크면_줄인다(self):
        out, err = self._prep(make_image('big.jpg', size=(4000, 3000)), max_px=2560)
        self.assertIsNone(err)
        self.assertLessEqual(max(Image.open(out).size), 2560)

    def test_빈_값은_조용히_넘어간다(self):
        self.assertEqual(self._prep(None), (None, None))

    # ── 어떤 형식이 올라오나 ──────────────────────────────

    def _mk(self, fmt, mode='RGB', size=(400, 300), **kw):
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        fill = (180, 90, 90) if mode in ('RGB', 'CMYK') else 128
        Image.new(mode, size, fill).save(buf, format=fmt, **kw)
        buf.seek(0)
        # content_type 을 일부러 틀리게 준다 — 브라우저를 안 믿는다는 뜻
        return SimpleUploadedFile('t.' + fmt.lower(), buf.read(),
                                  content_type='application/octet-stream')

    def test_흔한_형식은_다_올라간다(self):
        import pillow_heif
        pillow_heif.register_heif_opener()
        for fmt in ['JPEG', 'PNG', 'WEBP', 'GIF', 'BMP', 'TIFF', 'HEIF', 'AVIF']:
            with self.subTest(fmt):
                out, err = self._prep(self._mk(fmt), max_px=2560)
                self.assertIsNone(err, '%s 가 거부됐다: %s' % (fmt, err))
                self.assertIn(Image.open(out).format, ('JPEG', 'PNG', 'WEBP', 'GIF'))

    def test_cmyk는_rgb로_바뀐다(self):
        """포토샵에서 나온 인쇄용 JPEG. 그대로 두면 브라우저가 색을 뒤집는다"""
        out, err = self._prep(self._mk('JPEG', mode='CMYK'))
        self.assertIsNone(err)
        self.assertEqual(Image.open(out).mode, 'RGB')

    def test_투명_png는_투명하게_남는다(self):
        out, err = self._prep(self._mk('PNG', mode='RGBA'))
        self.assertIsNone(err)
        im = Image.open(out)
        self.assertEqual((im.format, im.mode), ('PNG', 'RGBA'))

    def test_움직이는_gif는_그대로_둔다(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        frames = [Image.new('P', (120, 80), i * 60) for i in range(1, 4)]
        frames[0].save(buf, format='GIF', save_all=True,
                       append_images=frames[1:], duration=200, loop=0)
        raw = buf.getvalue()
        out, err = self._prep(SimpleUploadedFile('a.gif', raw, content_type='image/gif'))
        self.assertIsNone(err)
        out.seek(0)
        self.assertEqual(out.read(), raw)   # 손대지 않았다


class CoordinateUploadTest(BaseTest):
    """좌표 글 — 여기엔 지금까지 아무 검사도 없었다"""

    def _post(self, **over):
        data = {
            'title': '사진 테스트', 'description': '설명',
            'latitude': '35.123456', 'longitude': '129.123456',
            'category': Coordinate.Category.MUSHROOM,
            'guest_nickname': '비회원', 'guest_password': 'pw1234',
        }
        data.update(over)
        return self.client.post(reverse('coordinates:create'), data)

    def test_아이폰_heic가_올라간다(self):
        r = self._post(images=make_heic())
        self.assertEqual(r.status_code, 302)
        img = CoordinateImage.objects.get()
        self.assertTrue(img.image.name.endswith('.jpg'), img.image.name)
        self.assertEqual(Image.open(img.image.path).format, 'JPEG')

    def test_눕힌_사진이_세워져_저장된다(self):
        self._post(images=make_rotated_image())
        img = CoordinateImage.objects.get()
        self.assertEqual(Image.open(img.image.path).size, (200, 400))

    def test_이미지가_아니면_글도_안_만들어진다(self):
        """뒤에서 걸러내면 사진 없는 빈 글만 남는다"""
        r = self._post(images=make_junk())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 0)
        self.assertEqual(CoordinateImage.objects.count(), 0)

    def test_용량이_넘으면_글도_안_만들어진다(self):
        r = self._post(images=make_oversized())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Coordinate.objects.count(), 0)

    def test_아주_큰_사진은_1280으로_줄어든다(self):
        from django.conf import settings as dj
        self._post(images=make_image('huge.jpg', size=(4000, 3000)))
        img = CoordinateImage.objects.get()
        self.assertLessEqual(max(Image.open(img.image.path).size), dj.IMAGE_MAX_PX)

    def test_올린_사진_이름이_글번호와_순서로_바뀐다(self):
        self._post(images=make_image('KakaoTalk_Photo_2026.jpg'))
        img = CoordinateImage.objects.get()
        name = os.path.basename(img.image.name)
        self.assertNotIn('KakaoTalk', name)
        self.assertIn('_%d_1' % img.coordinate_id, name)


class CommentUploadTest(BaseTest):
    """댓글 사진도 같은 규칙을 쓴다"""

    def _comment(self, photo):
        coord = self.make_coord(author=self.make_user())
        return self.client.post(reverse('comments:create', args=[coord.pk]), {
            'content': 'x', 'photo': photo,
            'guest_nickname': '비회원', 'guest_password': 'pw1234',
        })

    def test_아이폰_heic_댓글이_올라간다(self):
        """예전에는 content_type 때문에 막혔다"""
        self._comment(make_heic())
        c = Comment.objects.get()
        self.assertTrue(c.photo.name.endswith('.jpg'), c.photo.name)

    def test_눕힌_사진이_세워진다(self):
        self._comment(make_rotated_image())
        c = Comment.objects.get()
        self.assertEqual(Image.open(c.photo.path).size, (200, 400))

    def test_이미지가_아니면_댓글이_안_달린다(self):
        self._comment(make_junk())
        self.assertEqual(Comment.objects.count(), 0)


class UploadSizeTest(BaseTest):
    """올라온 사진을 가볍게 바꾸고 원본은 따로 보관한다

    PNG 가 그대로 통과하던 때 장당 평균 901KB 였다 (JPEG 는 395KB).
    1,010장이 쌓여 목록 한 페이지가 8.4MB 였다. 여기가 뚫리면 그게 다시 쌓인다.
    """

    def test_비치지_않는_png는_jpeg로_바뀐다(self):
        from apps.core.images import prepare_upload
        f = make_image('shot.png', size=(900, 600), fmt='PNG')
        ready, err = prepare_upload(f, max_px=1280, prefer_jpeg=True)

        self.assertIsNone(err)
        self.assertTrue(ready.name.endswith('.jpg'))

    def test_비치는_png는_png로_남는다(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.core.images import prepare_upload

        img = Image.new('RGBA', (300, 200), (255, 0, 0, 0))     # 완전 투명
        buf = BytesIO(); img.save(buf, 'PNG')
        f = SimpleUploadedFile('clear.png', buf.getvalue(), content_type='image/png')

        ready, err = prepare_upload(f, max_px=1280, prefer_jpeg=True)
        self.assertIsNone(err)
        self.assertTrue(ready.name.endswith('.png'))

    def test_prefer_jpeg를_안_켜면_png_그대로(self):
        from apps.core.images import prepare_upload
        f = make_image('shot.png', size=(900, 600), fmt='PNG')
        ready, err = prepare_upload(f, max_px=1280)
        self.assertTrue(ready.name.endswith('.png'))

    def test_움직이는_gif는_여전히_그대로_통과한다(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.core.images import prepare_upload

        frames = [Image.new('P', (60, 40), i) for i in (1, 2, 3)]
        buf = BytesIO()
        frames[0].save(buf, 'GIF', save_all=True, append_images=frames[1:], duration=80, loop=0)
        raw = buf.getvalue()
        f = SimpleUploadedFile('anim.gif', raw, content_type='image/gif')

        ready, err = prepare_upload(f, max_px=1280, prefer_jpeg=True)
        self.assertIsNone(err)
        ready.seek(0)
        self.assertEqual(ready.read(), raw)

    def test_원본은_media_바깥에_보관된다(self):
        import os
        from django.conf import settings
        from apps.core.images import archive_original

        path = archive_original(b'\x89PNG fake', 'phone.png', 'coordinates', '2026_11_17_01_02_03_7_1')
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith('2026_11_17_01_02_03_7_1.png'))
        # media 안에 있으면 nginx 가 열어버린다
        self.assertNotIn(str(settings.MEDIA_ROOT), path)

    def test_같은_이름으로_두_번_보관해도_원본을_안_덮는다(self):
        from apps.core.images import archive_original
        p1 = archive_original(b'first', 'a.png', 'coordinates', '2026_11_17_01_02_03_8_1')
        archive_original(b'second', 'a.png', 'coordinates', '2026_11_17_01_02_03_8_1')
        with open(p1, 'rb') as fh:
            self.assertEqual(fh.read(), b'first')


class CommentPhotoSizeTest(BaseTest):
    """댓글 사진도 좌표 글과 같은 규격을 쓴다

    2026-11-17 까지 댓글만 1920px / PNG 유지였다. 카톡 스크린샷이 PNG 로
    올라와서 65장에 56MB, 장당 평균 882KB 였다.
    """

    def _comment(self, photo):
        coord = self.make_coord(author=self.make_user())
        return self.client.post(reverse('comments:create', args=[coord.pk]), {
            'content': 'x', 'photo': photo,
            'guest_nickname': '비회원', 'guest_password': 'pw1234',
        })

    def test_댓글_png가_jpeg로_바뀐다(self):
        self._comment(make_image('shot.png', size=(900, 600), fmt='PNG'))
        c = Comment.objects.get()
        self.assertTrue(c.photo.name.endswith('.jpg'), c.photo.name)

    def test_댓글_사진도_1280으로_줄어든다(self):
        from django.conf import settings as dj
        self._comment(make_image('huge.jpg', size=(4000, 3000)))
        c = Comment.objects.get()
        self.assertLessEqual(max(Image.open(c.photo.path).size), dj.IMAGE_MAX_PX)

    def test_댓글_사진_이름이_작성시각과_댓글번호로_바뀐다(self):
        """같은 이름이 이미 있으면 Django 가 뒤에 무작위 글자를 붙인다.
        그래서 '끝이 _번호' 가 아니라 '_번호 가 들어 있다' 로 본다 —
        보관도 **실제로 저장된 이름**에서 뽑으므로 짝은 그래도 맞는다."""
        self._comment(make_image('KakaoTalk_Photo_2026.jpg'))
        c = Comment.objects.get()
        name = os.path.basename(c.photo.name)
        self.assertNotIn('KakaoTalk', name)
        self.assertRegex(name, r'^\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_%d(?=[._])' % c.pk)

    def test_댓글_원본이_media_바깥에_보관된다(self):
        import glob

        from django.conf import settings as dj
        self._comment(make_image('phone.png', size=(900, 600), fmt='PNG'))
        c = Comment.objects.get()
        stem = os.path.splitext(os.path.basename(c.photo.name))[0]
        found = glob.glob(os.path.join(str(dj.IMAGE_ORIGINALS_ROOT),
                                       'comments', stem + '.*'))
        self.assertTrue(found, '원본이 보관되지 않았다')
        # 원본은 PNG 그대로, 사이트에 나가는 건 JPEG
        self.assertTrue(found[0].endswith('.png'), found[0])
        self.assertTrue(c.photo.name.endswith('.jpg'), c.photo.name)
        self.assertNotIn(str(dj.MEDIA_ROOT), found[0])

    def test_사진_붙이기가_터져도_댓글_본문은_남는다(self):
        """사진은 댓글을 만든 뒤에 붙인다. 거기서 터지면 사진만 빠져야 한다"""
        from unittest import mock
        with mock.patch('apps.comments.views._attach_photo',
                        side_effect=OSError('디스크 꽉 찼다')):
            self._comment(make_image('x.jpg'))
        c = Comment.objects.get()
        self.assertEqual(c.content, 'x')
        self.assertFalse(c.photo)


class ProfilePhotoTest(BaseTest):
    """프로필 사진 — 2026-11-17 까지 검사가 **아무것도** 없었다

    `user.profile_image = request.FILES['profile_image']` 한 줄이 전부였다.
    그래서 아이폰 HEIC 가 깨진 채로 저장되고, 세워 찍은 사진이 눕고,
    용량 제한도 안 걸렸다. 이름 옆 동그라미로 쓰이는데 평균 708KB 였다.
    """

    def _save(self, photo=None, **extra):
        user = self.login()
        data = {'nickname': user.nickname, 'bio': '소개'}
        data.update(extra)
        if photo is not None:
            data['profile_image'] = photo
        self.client.post(reverse('accounts:my_settings'), data)
        user.refresh_from_db()
        return user

    def test_프로필은_512로_줄어든다(self):
        from django.conf import settings as dj
        user = self._save(make_image('big.jpg', size=(3000, 2000)))
        self.assertLessEqual(max(Image.open(user.profile_image.path).size),
                             dj.PROFILE_MAX_PX)

    def test_프로필_png가_jpeg로_바뀐다(self):
        user = self._save(make_image('shot.png', size=(900, 600), fmt='PNG'))
        self.assertTrue(user.profile_image.name.endswith('.jpg'),
                        user.profile_image.name)

    def test_프로필_아이폰_heic가_올라간다(self):
        user = self._save(make_heic())
        self.assertTrue(user.profile_image.name.endswith('.jpg'),
                        user.profile_image.name)
        self.assertEqual(Image.open(user.profile_image.path).format, 'JPEG')

    def test_프로필_눕힌_사진이_세워진다(self):
        user = self._save(make_rotated_image())
        w, h = Image.open(user.profile_image.path).size
        self.assertLess(w, h, '세로 사진이 눕은 채로 저장됐다')

    def test_프로필_이미지가_아니면_저장되지_않는다(self):
        user = self._save(make_junk())
        self.assertFalse(user.profile_image)

    def test_프로필_사진이_막혀도_닉네임은_저장된다(self):
        """사진 하나 때문에 닉네임·소개까지 날리면 억울하다"""
        user = self._save(make_junk(), nickname='바뀐이름')
        self.assertEqual(user.nickname, '바뀐이름')
        self.assertFalse(user.profile_image)

    def test_프로필_용량이_넘으면_막는다(self):
        user = self._save(make_oversized())
        self.assertFalse(user.profile_image)

    def test_프로필_원본이_media_바깥에_보관된다(self):
        import glob

        from django.conf import settings as dj
        user = self._save(make_image('me.png', size=(900, 600), fmt='PNG'))
        stem = os.path.splitext(os.path.basename(user.profile_image.name))[0]
        found = glob.glob(os.path.join(str(dj.IMAGE_ORIGINALS_ROOT),
                                       'profiles', stem + '.*'))
        self.assertTrue(found, '원본이 보관되지 않았다')
        self.assertNotIn(str(dj.MEDIA_ROOT), found[0])

    def test_프로필_이름이_올린시각과_회원번호로_바뀐다(self):
        user = self._save(make_image('KakaoTalk_Photo_2026.jpg'))
        name = os.path.basename(user.profile_image.name)
        self.assertNotIn('KakaoTalk', name)
        self.assertRegex(name,
                         r'^\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_%d(?=[._])' % user.pk)


class BragPhotoSizeTest(BaseTest):
    """자랑 게시판 — 워터마크를 넣은 뒤에도 가벼워야 한다"""

    def _post(self, image, watermark=False):
        data = {'caption': '자랑', 'guest_nickname': '비회원',
                'guest_password': 'pw1234', 'image': image}
        if watermark:
            data['watermark'] = 'on'
        return self.client.post(reverse('brag:create'), data)

    def test_자랑_png가_jpeg로_바뀐다(self):
        from apps.brag.models import BragPost
        self._post(make_image('shot.png', size=(900, 600), fmt='PNG'))
        post = BragPost.objects.get()
        self.assertTrue(post.image.name.endswith('.jpg'), post.image.name)

    def test_자랑_사진도_1280으로_줄어든다(self):
        from django.conf import settings as dj

        from apps.brag.models import BragPost
        self._post(make_image('huge.jpg', size=(4000, 3000)))
        post = BragPost.objects.get()
        self.assertLessEqual(max(Image.open(post.image.path).size), dj.IMAGE_MAX_PX)

    def test_워터마크를_넣어도_jpeg_품질이_걸린다(self):
        """예전에는 .png 로 저장돼서 quality=92 가 그냥 무시됐다"""
        from apps.brag.models import BragPost
        self._post(make_image('shot.png', size=(1200, 900), fmt='PNG'),
                   watermark=True)
        post = BragPost.objects.get()
        self.assertEqual(Image.open(post.image.path).format, 'JPEG')
        self.assertLess(os.path.getsize(post.image.path), 400 * 1024)

    def test_자랑_원본이_media_바깥에_보관된다(self):
        import glob

        from django.conf import settings as dj

        from apps.brag.models import BragPost
        self._post(make_image('phone.png', size=(900, 600), fmt='PNG'))
        post = BragPost.objects.get()
        stem = os.path.splitext(os.path.basename(post.image.name))[0]
        found = glob.glob(os.path.join(str(dj.IMAGE_ORIGINALS_ROOT),
                                       'brag', stem + '.*'))
        self.assertTrue(found, '원본이 보관되지 않았다')
        self.assertNotIn(str(dj.MEDIA_ROOT), found[0])


class FarmingPhotoSizeTest(BaseTest):
    """파밍 일지 사진도 같은 규격을 쓴다 (아직 올라온 게 없지만 규칙은 걸어둔다)"""

    def _journal(self, image):
        return self.client.post(reverse('farming:journal_create'), {
            'title': '파밍', 'content': '내용',
            'guest_nickname': '비회원', 'guest_password': 'pw1234',
            'image': image,
        })

    def test_파밍_png가_jpeg로_바뀐다(self):
        from apps.farming.models import FarmingJournal
        self._journal(make_image('shot.png', size=(900, 600), fmt='PNG'))
        j = FarmingJournal.objects.get()
        self.assertTrue(j.image.name.endswith('.jpg'), j.image.name)

    def test_파밍_사진도_1280으로_줄어든다(self):
        from django.conf import settings as dj

        from apps.farming.models import FarmingJournal
        self._journal(make_image('huge.jpg', size=(4000, 3000)))
        j = FarmingJournal.objects.get()
        self.assertLessEqual(max(Image.open(j.image.path).size), dj.IMAGE_MAX_PX)

    def test_파밍_원본이_media_바깥에_보관된다(self):
        import glob

        from django.conf import settings as dj

        from apps.farming.models import FarmingJournal
        self._journal(make_image('phone.png', size=(900, 600), fmt='PNG'))
        j = FarmingJournal.objects.get()
        stem = os.path.splitext(os.path.basename(j.image.name))[0]
        found = glob.glob(os.path.join(str(dj.IMAGE_ORIGINALS_ROOT),
                                       'farming', stem + '.*'))
        self.assertTrue(found, '원본이 보관되지 않았다')
        self.assertNotIn(str(dj.MEDIA_ROOT), found[0])
