"""업로드 이미지 손질 — 용량·형식 검사, HEIC 변환, EXIF 회전 보정.

좌표·댓글·자랑 세 군데가 같은 규칙을 써야 한다. 전에는 댓글만
content_type 으로 거르고 좌표는 아무 검사도 안 했다.

**content_type 은 못 믿는다.** 아이폰이 보내는 HEIC 는 브라우저에 따라
image/heic 이기도 하고 application/octet-stream 이기도 하다. 그래서
PIL 로 실제로 열어본다. 못 열면 이미지가 아니다.
"""
import io
import logging
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_BYTES = getattr(settings, 'MAX_UPLOAD_SIZE', 5 * 1024 * 1024)

# 그대로 저장해도 되는 형식. 손댈 이유가 없으면 다시 압축하지 않는다.
WEB_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}

# EXIF Orientation 태그 번호
_ORIENTATION = 0x0112


def _mb(n):
    return round(n / (1024 * 1024))


def _orientation_of(img):
    """세워 찍은 폰 사진은 눕혀 저장되고 회전 정보만 EXIF 에 들어온다."""
    try:
        return img.getexif().get(_ORIENTATION, 1) or 1
    except Exception:
        return 1


def prepare_upload(f, *, max_px=None):
    """업로드 파일을 검사하고 필요하면 바꿔서 돌려준다.

    반환: (파일, 오류메시지). 둘 중 하나는 항상 None 이다.
    - 용량 초과 / 이미지 아님 -> (None, 메시지)
    - 손댈 것 없음            -> (원본 그대로, None)
    - HEIC·회전·큰 사진       -> (새로 만든 JPEG, None)
    """
    if not f:
        return None, None

    if getattr(f, 'size', 0) > MAX_BYTES:
        return None, _('사진 용량은 %(mb)sMB를 넘을 수 없습니다.') % {'mb': _mb(MAX_BYTES)}

    try:
        f.seek(0)
        img = Image.open(f)
        img.load()
    except Exception as e:
        logger.info('이미지로 못 엶: %s (%s)', getattr(f, 'name', '?'), e)
        return None, _('이미지 파일이 아니거나 열 수 없는 형식입니다. '
                       '(JPG, PNG, WEBP, HEIC)')

    fmt = (img.format or '').upper()
    rotated = _orientation_of(img) != 1
    too_big = bool(max_px) and (img.width > max_px or img.height > max_px)

    # 손댈 게 없으면 원본을 그대로 쓴다. 괜히 다시 압축하면 화질만 깎인다.
    if fmt in WEB_FORMATS and not rotated and not too_big:
        f.seek(0)
        return f, None

    try:
        img = ImageOps.exif_transpose(img) or img      # 눕힌 사진 세우기
        if too_big:
            img.thumbnail((max_px, max_px), Image.LANCZOS)

        keep_png = (fmt == 'PNG')
        if not keep_png and img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')                   # JPEG 는 알파를 못 담는다

        buf = io.BytesIO()
        if keep_png:
            img.save(buf, 'PNG', optimize=True)
            ext = '.png'
        else:
            img.save(buf, 'JPEG', quality=90, optimize=True)
            ext = '.jpg'

        base = os.path.splitext(os.path.basename(getattr(f, 'name', 'photo')))[0]
        return ContentFile(buf.getvalue(), name=(base or 'photo') + ext), None
    except Exception as e:
        logger.warning('이미지 변환 실패: %s (%s)', getattr(f, 'name', '?'), e)
        return None, _('사진을 처리하지 못했습니다. 다른 사진으로 올려주세요.')
