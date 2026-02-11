"""게시글 수정 시 번역 캐시 삭제"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from .models import ContentTranslation


def clear_translation_cache(sender, instance, created, **kwargs):
    """수정 시(created=False) 기존 번역 캐시 삭제 → 다음 조회 시 원문 표시"""
    if created:
        return
    ct = ContentType.objects.get_for_model(instance)
    ContentTranslation.objects.filter(
        content_type=ct,
        object_id=instance.pk,
    ).delete()


# 번역 대상 모델들에 시그널 연결
# 앱이 로드된 뒤에 import 해야 하므로 try/except
try:
    from apps.coordinates.models import Coordinate
    post_save.connect(clear_translation_cache, sender=Coordinate)
except Exception:
    pass

try:
    from apps.comments.models import Comment
    post_save.connect(clear_translation_cache, sender=Comment)
except Exception:
    pass

try:
    from apps.farming.models import FarmingJournal, FarmingRequest, FarmingParticipation
    post_save.connect(clear_translation_cache, sender=FarmingJournal)
    post_save.connect(clear_translation_cache, sender=FarmingRequest)
    post_save.connect(clear_translation_cache, sender=FarmingParticipation)
except Exception:
    pass

try:
    from apps.core.models import Suggestion
    post_save.connect(clear_translation_cache, sender=Suggestion)
except Exception:
    pass
