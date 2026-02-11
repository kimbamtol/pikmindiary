from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class ContentTranslation(models.Model):
    """게시글 번역 캐시 - GenericForeignKey로 어떤 모델이든 번역 저장"""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    field_name = models.CharField(max_length=50)
    source_language = models.CharField(max_length=5)
    target_language = models.CharField(max_length=5)
    translated_text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '콘텐츠 번역'
        verbose_name_plural = '콘텐츠 번역'
        unique_together = ['content_type', 'object_id', 'field_name', 'target_language']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.content_type.model}#{self.object_id}.{self.field_name} → {self.target_language}"
