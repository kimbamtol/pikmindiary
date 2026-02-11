from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Report(models.Model):
    """신고"""
    
    class Reason(models.TextChoices):
        SPAM = 'SPAM', _('스팸/광고')
        WRONG_INFO = 'WRONG_INFO', _('잘못된 정보')
        INAPPROPRIATE = 'INAPPROPRIATE', _('부적절한 내용')
        OTHER = 'OTHER', _('기타')
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('대기')
        RESOLVED = 'RESOLVED', _('처리됨')
        DISMISSED = 'DISMISSED', _('기각')
    
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_made',
        verbose_name=_('신고자')
    )
    
    # 좌표 또는 댓글 중 하나만 선택
    coordinate = models.ForeignKey(
        'coordinates.Coordinate',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
        verbose_name=_('좌표')
    )
    comment = models.ForeignKey(
        'comments.Comment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
        verbose_name=_('댓글')
    )
    
    reason = models.CharField(
        _('신고 사유'),
        max_length=20,
        choices=Reason.choices
    )
    detail = models.TextField(
        _('상세 내용'),
        blank=True,
        max_length=500
    )
    
    status = models.CharField(
        _('처리 상태'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    admin_note = models.TextField(
        _('관리자 메모'),
        blank=True
    )
    
    created_at = models.DateTimeField(_('신고일'), auto_now_add=True)
    resolved_at = models.DateTimeField(_('처리일'), null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_resolved',
        verbose_name=_('처리자')
    )
    
    class Meta:
        verbose_name = _('신고')
        verbose_name_plural = _('신고들')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        target = self.coordinate or self.comment
        return f"[{self.get_reason_display()}] {target} - {self.get_status_display()}"
