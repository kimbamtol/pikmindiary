"""회귀 테스트 공통 바탕

모든 테스트가 상속하는 BaseTest가 세 가지를 책임진다.

1. 외부 API를 끊는다 - 좌표를 저장하면 Nominatim으로 지역을 조회하는 시그널이
   백그라운드 스레드로 뜬다. 테스트가 네트워크에 의존하면 안 되므로 막는다.
2. 업로드 파일을 임시 폴더로 보낸다 - 운영 media/ 를 건드리지 않는다.
3. 자주 쓰는 재료를 만들어 준다 - 회원, 좌표, 가짜 사진.
"""
import io
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.coordinates.models import Coordinate

User = get_user_model()

HOST = dict(HTTP_HOST='pikmindiary.com')


def make_image(name='test.jpg', size=(80, 60), fmt='JPEG'):
    """실제로 열리는 진짜 이미지 파일을 만든다.

    ImageField 검증과 워터마크(PIL)가 모두 실제 이미지를 요구하므로
    더미 바이트열로는 안 된다.
    """
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', size, (120, 180, 120)).save(buf, format=fmt)
    buf.seek(0)
    ctype = 'image/jpeg' if fmt == 'JPEG' else 'image/%s' % fmt.lower()
    return SimpleUploadedFile(name, buf.read(), content_type=ctype)


def make_heic(name='iphone.heic', size=(2000, 1200)):
    """아이폰이 올리는 HEIC 사진을 흉내 낸다.

    content_type 을 application/octet-stream 으로 두는 게 핵심이다 —
    브라우저가 실제로 그렇게 보내는 경우가 있고, 예전 검사는 그걸 막았다.
    """
    import pillow_heif
    pillow_heif.register_heif_opener()
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', size, (200, 80, 80)).save(buf, format='HEIF')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='application/octet-stream')


def make_rotated_image(name='sideways.jpg', size=(400, 200), orientation=6):
    """폰으로 세워 찍은 사진. 눕혀 저장되고 EXIF 에 회전값만 들어온다."""
    from PIL import Image

    buf = io.BytesIO()
    img = Image.new('RGB', size, (80, 80, 200))
    exif = img.getexif()
    exif[0x0112] = orientation          # Orientation 태그
    img.save(buf, format='JPEG', exif=exif)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')


def make_oversized(name='huge.jpg', mb=6):
    """용량 제한에 실제로 걸리는 파일. 내용은 중요하지 않다 —
    용량 검사가 디코딩보다 먼저 돌아야 한다는 게 요점이다."""
    return SimpleUploadedFile(name, b'\xff\xd8' + b'x' * (mb * 1024 * 1024),
                              content_type='image/jpeg')


def make_junk(name='bad.jpg', size_bytes=2000):
    """이미지가 아닌데 .jpg 를 뒤집어쓴 파일."""
    return SimpleUploadedFile(name, b'\x00NOT-AN-IMAGE' * (size_bytes // 13),
                              content_type='image/jpeg')


class BaseTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix='pd-test-media-')
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    def setUp(self):
        # 지역 자동 감지(Nominatim) 차단
        patcher = mock.patch('apps.coordinates.signals.update_coordinate_region_async')
        self.region_mock = patcher.start()
        self.addCleanup(patcher.stop)

        self.client = Client(**HOST)

    # ---------- 재료 ----------

    def make_user(self, nickname=None, **kw):
        # nickname은 유일해야 한다. 이름을 안 주면 번호를 붙여 만든다.
        n = User.objects.count() + 1
        if nickname is None:
            nickname = '테스터%d' % n
        elif User.objects.filter(nickname=nickname).exists():
            nickname = '%s%d' % (nickname, n)
        return User.objects.create_user(
            username=kw.pop('username', 'user%d' % n),
            email=kw.pop('email', 'user%d@example.com' % n),
            password=kw.pop('password', 'pw-for-test-1234'),
            nickname=nickname,
            **kw
        )

    def make_coord(self, author=None, title='테스트 좌표', **kw):
        return Coordinate.objects.create(
            author=author,
            title=title,
            latitude=kw.pop('latitude', '35.123456'),
            longitude=kw.pop('longitude', '129.123456'),
            category=kw.pop('category', Coordinate.Category.MUSHROOM),
            status=kw.pop('status', Coordinate.Status.APPROVED),
            approved_at=timezone.now(),
            **kw
        )

    def login(self, user=None):
        user = user or self.make_user()
        self.client.force_login(user)
        return user
