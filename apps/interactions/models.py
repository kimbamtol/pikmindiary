from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Like(models.Model):
    """좋아요"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('사용자')
    )
    coordinate = models.ForeignKey(
        'coordinates.Coordinate',
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('좌표')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('좋아요')
        verbose_name_plural = _('좋아요들')
        unique_together = ['user', 'coordinate']
        indexes = [
            models.Index(fields=['user', 'coordinate']),
            models.Index(fields=['coordinate', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.nickname} → {self.coordinate.title}"


class Bookmark(models.Model):
    """북마크"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookmarks',
        verbose_name=_('사용자')
    )
    coordinate = models.ForeignKey(
        'coordinates.Coordinate',
        on_delete=models.CASCADE,
        related_name='bookmarks',
        verbose_name=_('좌표')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('북마크')
        verbose_name_plural = _('북마크들')
        unique_together = ['user', 'coordinate']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.nickname} ★ {self.coordinate.title}"


class CommentLike(models.Model):
    """댓글 좋아요"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comment_likes',
        verbose_name=_('사용자')
    )
    comment = models.ForeignKey(
        'comments.Comment',
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('댓글')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('댓글 좋아요')
        verbose_name_plural = _('댓글 좋아요들')
        unique_together = ['user', 'comment']
        indexes = [
            models.Index(fields=['user', 'comment']),
            models.Index(fields=['comment', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.nickname} → Comment #{self.comment.pk}"


class Notification(models.Model):
    """알림 (좋아요, 댓글, 복사 마일스톤)"""

    class NotificationType(models.TextChoices):
        LIKE = 'LIKE', _('좋아요')
        COMMENT = 'COMMENT', _('댓글')
        COPY_MILESTONE = 'COPY_MILESTONE', _('복사 마일스톤')
        SUGGESTION_REPLY = 'SUGGESTION_REPLY', _('건의사항 답변')
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('수신자')
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_notifications',
        null=True,
        blank=True,
        verbose_name=_('발신자')
    )
    notification_type = models.CharField(
        _('알림 유형'),
        max_length=20,
        choices=NotificationType.choices
    )
    coordinate = models.ForeignKey(
        'coordinates.Coordinate',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('좌표'),
        null=True,
        blank=True
    )
    message = models.TextField(_('메시지'))
    is_read = models.BooleanField(_('읽음 여부'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('알림')
        verbose_name_plural = _('알림들')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.recipient.nickname}: {self.message[:30]}"
