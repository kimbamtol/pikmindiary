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
    brag_post = models.ForeignKey(
        'brag.BragPost',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='comments',
        verbose_name=_('자랑 글')
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
        self._shrink_photo()

    def _shrink_photo(self):
        """큰 사진을 1920px 안으로 줄인다.

        여기서 예외가 나가면 안 된다. super().save() 가 이미 끝난 뒤라
        댓글은 DB에 들어갔는데 사용자는 500만 보게 된다 —
        실제로 그래서 같은 댓글을 두 번 쓰고 지우지도 못한 분이 있었다.
        """
        if not self.photo:
            return
        try:
            img_path = self.photo.path
            img = Image.open(img_path)
            max_w, max_h = 1920, 1920
            if img.width > max_w or img.height > max_h:
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')   # JPEG 는 알파를 못 담는다
                img.save(img_path, optimize=True, quality=85)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                '댓글 사진 축소 실패 (댓글은 저장됨) pk=%s: %s', self.pk, e)
