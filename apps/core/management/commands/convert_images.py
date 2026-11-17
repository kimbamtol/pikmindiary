"""올라온 사진을 가볍게 바꾸고 원본은 따로 보관한다.

왜 하나:
  좌표 목록 한 페이지(20장)가 8.4MB 였다. 썸네일이 없어서 원본을 그대로
  내려주고 CSS 로만 줄여 보여줬기 때문이다. 게다가 1,010장이 PNG 라
  (카톡 사진·휴대폰 스크린샷) 장당 평균 901KB 였다.

무엇을 하나:
  1) 원본을 image_originals/ 로 복사한다 (media 바깥 - 밖에서 접근 불가).
  2) 1280px / 품질 82 progressive JPEG 로 바꿔 media/ 에 저장한다.
  3) DB 의 사진 경로를 새 이름으로 고친다.
  4) 원래 파일을 지운다 (원본은 1) 에 남아 있다).

이름:
  2026_11_17_13_50_42_612_1.jpg  =  글 작성시각 _ 글번호 _ 사진순서
  원본과 변환본이 같은 이름이라 짝이 저절로 맞는다. 그래서 변환 기록표가 따로 필요없다.
  보관 폴더에 있으면 '이미 변환한 것' 이므로 중간에 멈춰도 다시 돌리면 이어서 한다.

안전:
  새 파일을 쓰고 -> DB 를 고치고 -> 옛 파일을 지운다. 이 순서라서 어느 순간에
  멈춰도 DB 가 가리키는 파일은 항상 존재한다. 운영 중에 돌려도 사진이 안 깨진다.
  변환 결과가 원본보다 크면 (이미 잘 압축된 작은 사진) 원본을 그대로 쓴다.
"""
import glob
import io
import os
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageFile, ImageOps

# 업로드가 중간에 끊겨 파일 끝이 잘린 사진이 2장 있다. 브라우저는 보여주는데
# PIL 은 기본값으로 거부한다. 보이는 데까지라도 살려서 변환한다.
ImageFile.LOAD_TRUNCATED_IMAGES = True

from apps.coordinates.models import CoordinateImage


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f}{unit}' if unit == 'B' else f'{n:.1f}{unit}'
        n /= 1024


class Command(BaseCommand):
    help = '좌표 사진을 1280px/q82 로 변환하고 원본을 image_originals/ 에 보관한다'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='이 장수만 처리 (시험용)')
        parser.add_argument('--dry-run', action='store_true', help='바꾸지 않고 결과만 본다')
        parser.add_argument('--max-px', type=int, default=settings.IMAGE_MAX_PX)
        parser.add_argument('--quality', type=int, default=settings.IMAGE_QUALITY)

    def handle(self, *args, **opts):
        limit = opts['limit']
        dry = opts['dry_run']
        max_px = opts['max_px']
        quality = opts['quality']

        originals_root = str(settings.IMAGE_ORIGINALS_ROOT)
        os.makedirs(originals_root, exist_ok=True)

        qs = (CoordinateImage.objects
              .select_related('coordinate')
              .order_by('coordinate_id', 'id'))

        # 글마다 사진 순서를 매긴다
        order = {}
        for im in qs:
            order.setdefault(im.coordinate_id, []).append(im.pk)

        done = skipped = missing = kept = failed = 0
        before_total = after_total = 0
        n = 0

        for im in qs:
            if limit and n >= limit:
                break

            coord = im.coordinate
            if coord is None:
                missing += 1
                continue

            try:
                old_path = im.image.path
            except Exception:
                missing += 1
                continue

            if not os.path.exists(old_path):
                missing += 1
                continue

            idx = order[im.coordinate_id].index(im.pk) + 1
            created = timezone.localtime(coord.created_at)
            stem = f'{created:%Y_%m_%d_%H_%M_%S}_{coord.pk}_{idx}'

            src_ext = os.path.splitext(old_path)[1].lower() or '.jpg'
            archive_dir = os.path.join(originals_root, 'coordinates')
            archive_path = os.path.join(archive_dir, f'{stem}{src_ext}')

            # 이미 보관돼 있으면 처리한 사진이다.
            # 확장자가 바뀌는 경우(png -> jpg)가 있으므로 이름만 보고 찾는다.
            # 확장자까지 맞춰 찾으면 이미 바꾼 사진을 또 바꿔서 두 번 압축된다.
            if glob.glob(os.path.join(glob.escape(archive_dir), glob.escape(stem) + '.*')):
                skipped += 1
                continue

            before = os.path.getsize(old_path)
            n += 1

            try:
                with Image.open(old_path) as img:
                    img = ImageOps.exif_transpose(img)
                    img = img.convert('RGB')
                    if max(img.size) > max_px:
                        img.thumbnail((max_px, max_px), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, 'JPEG', quality=quality,
                             optimize=True, progressive=True)
                new_bytes = buf.getvalue()
            except Exception as e:
                failed += 1
                self.stderr.write(f'  실패 #{im.pk} {old_path}: {e}')
                continue

            # 변환해서 더 커지면 원본을 그대로 쓴다
            use_original = len(new_bytes) >= before
            new_ext = src_ext if use_original else '.jpg'
            after = before if use_original else len(new_bytes)

            before_total += before
            after_total += after
            if use_original:
                kept += 1

            if dry:
                continue

            # 1) 원본 보관
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)
            shutil.copy2(old_path, archive_path)

            # 2) 새 파일 저장
            rel_dir = 'coordinates'
            new_rel = f'{rel_dir}/{stem}{new_ext}'
            new_path = os.path.join(settings.MEDIA_ROOT, new_rel)
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            if use_original:
                if os.path.abspath(old_path) != os.path.abspath(new_path):
                    shutil.copy2(old_path, new_path)
            else:
                with open(new_path, 'wb') as f:
                    f.write(new_bytes)

            # 3) DB 수정 (여기까지 오면 새 파일이 이미 있다)
            CoordinateImage.objects.filter(pk=im.pk).update(image=new_rel)

            # 4) 옛 파일 삭제 (원본은 1) 에 있다)
            if os.path.abspath(new_path) != os.path.abspath(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

            done += 1
            if done % 200 == 0:
                self.stdout.write(f'  ... {done}장')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('시험 결과' if dry else '변환 완료'))
        self.stdout.write(f'  처리   {done if not dry else n}장')
        self.stdout.write(f'  건너뜀 {skipped}장 (이미 변환됨)')
        self.stdout.write(f'  파일없음 {missing}장')
        self.stdout.write(f'  원본유지 {kept}장 (변환하면 더 커져서)')
        self.stdout.write(f'  실패   {failed}장')
        if before_total:
            self.stdout.write(
                f'  용량   {human(before_total)} → {human(after_total)}'
                f'  ({100 * (1 - after_total / before_total):.0f}% 감소)')
