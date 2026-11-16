"""업로드 사진 — 용량·형식 검사, HEIC 변환, 눕힌 사진 세우기.

2026-11-16에 셋을 한꺼번에 넣었다.
1. 좌표 업로드에 검사가 아예 없었다 (댓글만 있었다)
2. 아이폰 HEIC 를 서버가 못 열어서 깨진 채로 저장됐다
3. 세워 찍은 폰 사진이 눕혀서 올라갔다
"""
import io

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

    def test_아주_큰_사진은_2560으로_줄어든다(self):
        self._post(images=make_image('huge.jpg', size=(4000, 3000)))
        img = CoordinateImage.objects.get()
        self.assertLessEqual(max(Image.open(img.image.path).size), 2560)


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
