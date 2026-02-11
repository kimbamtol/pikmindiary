"""기존 게시글 일괄 번역 관리 명령어

사용법:
    python manage.py translate_existing --model coordinates.Coordinate --fields title,description,postcard_name --batch 50
    python manage.py translate_existing --model comments.Comment --fields content --batch 50
    python manage.py translate_existing --model farming.FarmingJournal --fields title,content --batch 50
"""
from django.core.management.base import BaseCommand
from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from apps.translations.models import ContentTranslation
from apps.translations.services import translate_on_create, SUPPORTED_LANGS


class Command(BaseCommand):
    help = '기존 게시글을 일괄 번역합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            required=True,
            help='번역할 모델 (예: coordinates.Coordinate)',
        )
        parser.add_argument(
            '--fields',
            required=True,
            help='번역할 필드 목록 (쉼표 구분, 예: title,description)',
        )
        parser.add_argument(
            '--batch',
            type=int,
            default=50,
            help='배치 크기 (기본: 50)',
        )

    def handle(self, *args, **options):
        model_label = options['model']
        fields = options['fields'].split(',')
        batch_size = options['batch']

        try:
            Model = apps.get_model(model_label)
        except LookupError:
            self.stderr.write(self.style.ERROR(f"모델 '{model_label}'을 찾을 수 없습니다."))
            return

        ct = ContentType.objects.get_for_model(Model)

        # 번역이 없는 객체 찾기 - 첫 번째 필드와 첫 번째 타겟 언어 기준
        already_translated_ids = ContentTranslation.objects.filter(
            content_type=ct,
            field_name=fields[0],
        ).values_list('object_id', flat=True).distinct()

        queryset = Model.objects.exclude(pk__in=already_translated_ids)
        total = queryset.count()

        self.stdout.write(f"번역 대상: {total}개 ({model_label})")

        translated = 0
        for obj in queryset[:batch_size]:
            try:
                translate_on_create(obj, fields)
                translated += 1
                self.stdout.write(f"  [{translated}/{min(total, batch_size)}] {obj} 번역 완료")
            except Exception as e:
                self.stderr.write(f"  오류: {obj} - {e}")

        self.stdout.write(self.style.SUCCESS(
            f"\n완료: {translated}개 번역됨 (전체 {total}개 중 배치 {batch_size}개)"
        ))
