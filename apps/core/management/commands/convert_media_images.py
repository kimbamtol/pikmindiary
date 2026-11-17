"""댓글·자랑·파밍·프로필 사진을 가볍게 바꾸고 원본은 따로 보관한다.

좌표 글 사진은 `convert_images` 가 먼저 했다 (2,888장, 1.6GB → 321MB).
그때 나머지 네 곳은 손대지 않았는데, 규칙이 제각각이었다.

  댓글   1920px, PNG 는 PNG 그대로   → 65장 / 56MB / 평균 882KB
  자랑   2560px, 워터마크 후 품질 92 → 13장 / 10MB / 평균 787KB
  파밍   2560px                      → 0장
  프로필 **검사가 아예 없었다**      → 39장 / 27MB / 평균 708KB

프로필은 이름 옆 동그라미로 40px 쯤으로 보이는데 708KB 를 받고 있었다.
제일 크게 쓰이는 데가 프로필 화면의 160px 이라 512px 로 줄인다.

하는 일과 순서는 `convert_images` 와 똑같다.

  1) 원본을 image_originals/<곳>/ 로 복사한다 (media 바깥 - 밖에서 못 받는다)
  2) 1280px(프로필은 512px) / 품질 82 progressive JPEG 로 바꿔 media/ 에 저장
  3) DB 의 경로를 새 이름으로 고친다
  4) 옛 파일을 지운다 (원본은 1) 에 남아 있다)

이 순서라서 어느 순간에 멈춰도 DB 가 가리키는 파일은 항상 존재한다.
보관 폴더에 같은 이름이 있으면 '이미 한 것' 이므로 다시 돌리면 이어서 한다.
확장자가 바뀌니까(png → jpg) **이름만** 보고 찾는다 - 확장자까지 맞춰 찾으면
이미 바꾼 사진을 또 바꿔서 두 번 압축된다. 좌표 때 실제로 10장이 그랬다.

비치는 PNG 는 PNG 로 남긴다. 좌표 사진 1,010장은 전부 안 비쳐서 그냥 JPEG 로
바꿨지만, 프로필엔 투명 배경 캐릭터가 있을 수 있다.

자랑 글 사진은 워터마크가 이미 박힌 파일이다. 박히기 전의 원본은 남아 있지
않으므로, 보관되는 것도 '워터마크가 박힌 상태' 다.
"""
import glob
import io
import os
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageFile, ImageOps

# 끝이 잘린 파일이 있어도 보이는 데까지 살려서 변환한다 (좌표에서 2장 나왔다)
ImageFile.LOAD_TRUNCATED_IMAGES = True

from apps.core.images import has_transparency


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f}{unit}' if unit == 'B' else f'{n:.1f}{unit}'
        n /= 1024


def _stem_from_created(obj, field_name):
    """'작성시각_번호'. 새로 올라오는 사진과 같은 규칙이다."""
    made = timezone.localtime(obj.created_at)
    return f'{made:%Y_%m_%d_%H_%M_%S}_{obj.pk}'


def _stem_from_mtime(obj, field_name):
    """프로필 사진은 언제 올렸는지 DB 에 없다. 파일 수정시각을 쓴다."""
    try:
        ts = os.path.getmtime(getattr(obj, field_name).path)
        made = timezone.localtime(timezone.datetime.fromtimestamp(
            ts, tz=timezone.get_current_timezone()))
    except Exception:
        made = timezone.localtime()
    return f'{made:%Y_%m_%d_%H_%M_%S}_{obj.pk}'


# (이름, 모델경로, 필드, 저장폴더, 최대크기설정, 이름만드는함수)
TARGETS = [
    ('댓글',   'comments.Comment',      'photo',         'comment_photos', 'IMAGE_MAX_PX',  _stem_from_created),
    ('자랑',   'brag.BragPost',         'image',         'brag',           'IMAGE_MAX_PX',  _stem_from_created),
    ('파밍',   'farming.FarmingJournal', 'image',        'farming',        'IMAGE_MAX_PX',  _stem_from_created),
    ('프로필', 'accounts.CustomUser',   'profile_image', 'profiles',       'PROFILE_MAX_PX', _stem_from_mtime),
]


class Command(BaseCommand):
    help = '댓글·자랑·파밍·프로필 사진을 변환하고 원본을 image_originals/ 에 보관한다'

    def add_arguments(self, parser):
        parser.add_argument('--only', default='', help='한 곳만 (comments|brag|farming|profiles)')
        parser.add_argument('--limit', type=int, default=0, help='곳마다 이 장수만 (시험용)')
        parser.add_argument('--dry-run', action='store_true', help='바꾸지 않고 결과만 본다')
        parser.add_argument('--quality', type=int, default=settings.IMAGE_QUALITY)

    def handle(self, *args, **opts):
        from django.apps import apps as django_apps

        only = opts['only'].strip()
        total_before = total_after = 0
        grand = {'done': 0, 'skipped': 0, 'missing': 0, 'kept': 0, 'failed': 0}

        for label, model_path, field, subdir, max_setting, stem_fn in TARGETS:
            if only and only not in (subdir, label):
                continue

            app_label, model_name = model_path.split('.')
            Model = django_apps.get_model(app_label, model_name)
            max_px = getattr(settings, max_setting)

            stats, before, after = self._convert(
                Model, field, subdir, max_px, opts['quality'],
                stem_fn, opts['limit'], opts['dry_run'],
            )

            total_before += before
            total_after += after
            for k in grand:
                grand[k] += stats[k]

            line = (f'{label:4s} 처리 {stats["done"]:3d}  '
                    f'건너뜀 {stats["skipped"]:3d}  '
                    f'파일없음 {stats["missing"]:3d}  '
                    f'원본유지 {stats["kept"]:3d}  '
                    f'실패 {stats["failed"]:3d}')
            if before:
                line += (f'   {human(before)} → {human(after)}'
                         f' ({100 * (1 - after / before):.0f}% 감소)')
            self.stdout.write(line)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('시험 결과' if opts['dry_run'] else '변환 완료'))
        for k, ko in [('done', '처리'), ('skipped', '건너뜀(이미 변환됨)'),
                      ('missing', '파일없음'), ('kept', '원본유지(변환하면 더 커져서)'),
                      ('failed', '실패')]:
            self.stdout.write(f'  {ko} {grand[k]}장')
        if total_before:
            self.stdout.write(
                f'  용량 {human(total_before)} → {human(total_after)}'
                f'  ({100 * (1 - total_after / total_before):.0f}% 감소)')

    # ------------------------------------------------------------------

    def _convert(self, Model, field, subdir, max_px, quality, stem_fn, limit, dry):
        stats = {'done': 0, 'skipped': 0, 'missing': 0, 'kept': 0, 'failed': 0}
        before_total = after_total = 0

        originals_root = str(settings.IMAGE_ORIGINALS_ROOT)
        archive_dir = os.path.join(originals_root, subdir)

        qs = (Model.objects.exclude(**{field: ''})
              .exclude(**{f'{field}__isnull': True})
              .order_by('pk'))

        n = 0
        for obj in qs.iterator():
            if limit and n >= limit:
                break

            f = getattr(obj, field)
            try:
                old_path = f.path
            except Exception:
                stats['missing'] += 1
                continue
            if not os.path.exists(old_path):
                stats['missing'] += 1
                continue

            stem = stem_fn(obj, field)
            src_ext = os.path.splitext(old_path)[1].lower() or '.jpg'

            # 이름만 보고 찾는다 (확장자가 바뀌므로)
            if glob.glob(os.path.join(glob.escape(archive_dir),
                                      glob.escape(stem) + '.*')):
                stats['skipped'] += 1
                continue

            before = os.path.getsize(old_path)
            n += 1

            try:
                with Image.open(old_path) as img:
                    keep_png = (img.format or '').upper() == 'PNG' and has_transparency(img)
                    img = ImageOps.exif_transpose(img) or img
                    if max(img.size) > max_px:
                        img.thumbnail((max_px, max_px), Image.LANCZOS)
                    buf = io.BytesIO()
                    if keep_png:
                        if img.mode not in ('RGBA', 'LA', 'P', 'RGB', 'L'):
                            img = img.convert('RGBA')
                        img.save(buf, 'PNG', optimize=True)
                        out_ext = '.png'
                    else:
                        if img.mode not in ('RGB', 'L'):
                            img = img.convert('RGB')
                        img.save(buf, 'JPEG', quality=quality,
                                 optimize=True, progressive=True)
                        out_ext = '.jpg'
                new_bytes = buf.getvalue()
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(f'  실패 {Model.__name__}#{obj.pk} {old_path}: {e}')
                continue

            # 변환해서 더 커지면 원본을 그대로 쓴다
            use_original = len(new_bytes) >= before
            new_ext = src_ext if use_original else out_ext
            after = before if use_original else len(new_bytes)

            before_total += before
            after_total += after
            if use_original:
                stats['kept'] += 1

            if dry:
                continue

            # 1) 원본 보관
            os.makedirs(archive_dir, exist_ok=True)
            archive_path = os.path.join(archive_dir, f'{stem}{src_ext}')
            shutil.copy2(old_path, archive_path)

            # 2) 새 파일 저장
            new_rel = f'{subdir}/{stem}{new_ext}'
            new_path = os.path.join(settings.MEDIA_ROOT, new_rel)
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            if use_original:
                if os.path.abspath(old_path) != os.path.abspath(new_path):
                    shutil.copy2(old_path, new_path)
            else:
                with open(new_path, 'wb') as fh:
                    fh.write(new_bytes)

            # 3) DB 수정 (여기까지 오면 새 파일이 이미 있다)
            Model.objects.filter(pk=obj.pk).update(**{field: new_rel})

            # 4) 옛 파일 삭제 (원본은 1) 에 있다)
            if os.path.abspath(new_path) != os.path.abspath(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

            stats['done'] += 1

        return stats, before_total, after_total
