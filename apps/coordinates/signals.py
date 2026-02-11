"""Signals for coordinates app"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Coordinate
from .region_utils import update_coordinate_region_async


@receiver(post_save, sender=Coordinate)
def update_region_after_save(sender, instance, created, **kwargs):
    """
    게시글 저장 후 Nominatim API로 정확한 지역 감지
    - 새로 생성된 경우에만 실행
    - 백그라운드에서 비동기로 처리
    """
    if created:
        # 새 게시글일 때만 API 호출 (수정 시에는 호출 안 함)
        update_coordinate_region_async(instance.pk)
