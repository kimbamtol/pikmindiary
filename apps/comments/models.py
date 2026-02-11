from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from PIL import Image
import os


class Comment(models.Model):
    """댓글 (대댓글 지원)"""

    coordinate = models.ForeignKey(
        'coordinates.Coordinate',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='comments',
        verbose_name=_('좌표')
    )
    farming_journal = models.ForeignKey(
        'farming.FarmingJournal',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='comments',
        verbose_name=_('농사 일지')
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='comments',
        verbose_name=_('작성자')
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_('부모 댓글')
    )

    content = models.TextField(_('내용'), max_length=500, blank=True)

    # 사진 첨부
    photo = models.ImageField(
        _('사진'),
        upload_to='comment_photos/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text=_('댓글에 첨부할 사진 (최대 5MB, JPG/PNG/WEBP)')
    )

    # 비회원 작성용
    guest_nickname = models.CharField(
        _('비회원 닉네임'),
        max_length=30,
        blank=True
    )
    guest_password = models.CharField(
        _('비회원 비밀번호'),
        max_length=128,
        blank=True
    )

    is_deleted = models.BooleanField(_('삭제됨'), default=False)

    created_at = models.DateTimeField(_('작성일'), auto_now_add=True)
    updated_at = models.DateTimeField(_('수정일'), auto_now=True)
    
    class Meta:
        verbose_name = _('댓글')
        verbose_name_plural = _('댓글들')
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['coordinate', 'created_at']),
            models.Index(fields=['farming_journal', 'created_at']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        author_name = self.author.nickname if self.author else self.guest_nickname
        content_preview = self.content[:30] + '...' if len(self.content) > 30 else self.content
        return f"{author_name}: {content_preview}"
    
    @property
    def display_name(self):
        """표시용 이름"""
        if self.author:
            return self.author.nickname
        return self.guest_nickname or '익명'
    
    @property
    def is_reply(self):
        """대댓글인지 여부"""
        return self.parent is not None

    @property
    def has_photo(self):
        """사진이 첨부되어 있는지 여부"""
        return bool(self.photo)

    @property
    def like_count(self):
        """댓글 좋아요 수"""
        return self.likes.count()

    def save(self, *args, **kwargs):
        """저장 시 이미지 리사이징"""
        super().save(*args, **kwargs)

        if self.photo:
            img_path = self.photo.path
            img = Image.open(img_path)

            # 최대 크기 제한 (1920px)
            max_size = (1920, 1920)
            if img.height > max_size[0] or img.width > max_size[1]:
                img.thumbnail(max_size, Image.Lanczos)
                img.save(img_path, optimize=True, quality=85)
