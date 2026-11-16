"""사진 업로드

아이폰 HEIC처럼 브라우저가 변환해 주는 부분은 서버에서 재현할 수 없다.
여기서 지키는 것은 '올린 장수만큼 저장되고, 5장을 넘지 않고, 워터마크를 켜면
이미지가 깨지지 않고 남는다'이다.
"""
from django.urls import reverse

from apps.coordinates.models import Coordinate, CoordinateImage

from .base import BaseTest, make_image


class UploadTest(BaseTest):
    def post_data(self, **kw):
        data = {
            'title': '사진 있는 글',
            'description': '',
            'postcard_name': '',
            'latitude': '35.1',
            'longitude': '129.1',
            'category': Coordinate.Category.MUSHROOM,
        }
        data.update(kw)
        return data

    def test_사진_한_장을_올린다(self):
        self.login(self.make_user())
        self.client.post(reverse('coordinates:create'),
                         self.post_data(images=make_image('a.jpg')))

        coord = Coordinate.objects.get(title='사진 있는 글')
        self.assertEqual(coord.images.count(), 1)
        self.assertTrue(coord.images.first().image.name.endswith('.jpg'))

    def test_여러_장을_올리면_순서가_붙는다(self):
        self.login(self.make_user())
        self.client.post(reverse('coordinates:create'), self.post_data(
            images=[make_image('a.jpg'), make_image('b.jpg'), make_image('c.jpg')]))

        coord = Coordinate.objects.get(title='사진 있는 글')
        self.assertEqual(coord.images.count(), 3)
        self.assertEqual([i.order for i in coord.images.all()], [0, 1, 2])

    def test_여섯_장을_올려도_다섯_장만_저장된다(self):
        self.login(self.make_user())
        self.client.post(reverse('coordinates:create'), self.post_data(
            images=[make_image('%d.jpg' % i) for i in range(6)]))

        coord = Coordinate.objects.get(title='사진 있는 글')
        self.assertEqual(coord.images.count(), 5)

    def test_png도_올라간다(self):
        self.login(self.make_user())
        self.client.post(reverse('coordinates:create'),
                         self.post_data(images=make_image('a.png', fmt='PNG')))
        self.assertEqual(Coordinate.objects.get(title='사진 있는 글').images.count(), 1)

    def test_워터마크를_켜도_이미지가_살아있다(self):
        """PIL로 다시 그려 저장하므로, 깨지면 여기서 걸린다"""
        from PIL import Image

        self.login(self.make_user(nickname='워터마크주인'))
        self.client.post(reverse('coordinates:create'), self.post_data(
            images=make_image('a.jpg'), watermark_enabled='on'))

        coord = Coordinate.objects.get(title='사진 있는 글')
        self.assertTrue(coord.watermark_enabled)

        img = coord.images.first()
        with Image.open(img.image.path) as im:
            im.verify()                      # 깨진 파일이면 예외가 난다
        self.assertGreater(img.image.size, 0)

    def test_사진_없이도_글은_써진다(self):
        self.login(self.make_user())
        self.client.post(reverse('coordinates:create'), self.post_data())
        self.assertEqual(Coordinate.objects.get(title='사진 있는 글').images.count(), 0)

    def test_글을_지우면_이미지도_지워진다(self):
        user = self.login(self.make_user())
        self.client.post(reverse('coordinates:create'),
                         self.post_data(images=make_image('a.jpg')))
        coord = Coordinate.objects.get(title='사진 있는 글')
        self.assertEqual(CoordinateImage.objects.count(), 1)

        self.client.post(reverse('coordinates:delete', args=[coord.pk]))
        self.assertEqual(CoordinateImage.objects.count(), 0)
