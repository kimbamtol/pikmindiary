"""Brag models - 피크민 자랑 (엽서·피크민 사진 자랑 게시판)"""
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class BragPost(models.Model):
    """자랑 글 - 사진 한 장 + 한마디"""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='brag_posts',
        verbose_name=_('작성자')
    )
    guest_nickname = models.CharField(_('비회원 닉네임'), max_length=30, blank=True)
    guest_password = models.CharField(_('비회원 비밀번호'), max_length=128, blank=True)

    image = models.ImageField(_('사진'), upload_to='brag/%Y/%m/')
    caption = models.CharField(_('한마디'), max_length=200, blank=True)

    watermark_enabled = models.BooleanField(
        _('워터마크'), default=True,
        help_text=_('사진에 닉네임 워터마크를 넣습니다.')
    )

    like_count = models.PositiveIntegerField(_('좋아요 수'), default=0)
    comment_count = models.PositiveIntegerField(_('댓글 수'), default=0)
    view_count = models.PositiveIntegerField(_('조회수'), default=0)

    is_hidden = models.BooleanField(_('숨김'), default=False, help_text=_('관리자가 숨긴 글은 목록에 보이지 않습니다.'))

    created_at = models.DateTimeField(_('작성일'), auto_now_add=True)
    updated_at = models.DateTimeField(_('수정일'), auto_now=True)

    class Meta:
        verbose_name = _('자랑 글')
        verbose_name_plural = _('자랑 글')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['-like_count']),
        ]

    def __str__(self):
        return f'{self.display_name} - {self.caption[:20] or "사진"}'

    @property
    def display_name(self):
        if self.author:
            return self.author.nickname
        return self.guest_nickname or _('익명')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.watermark_enabled and self.image:
            self._apply_watermark()

    def _apply_watermark(self):
        """사진 오른쪽 아래에 닉네임 워터마크"""
        from PIL import Image, ImageDraw, ImageFont

        try:
            path = self.image.path
            img = Image.open(path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            text = self.display_name or '피크민다이어리'
            layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(layer)

            font_size = max(18, int(img.width * 0.035))
            for font_path in (
                '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
                '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            ):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except OSError:
                    continue
            else:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            margin = max(12, int(img.width * 0.02))
            x, y = img.width - tw - margin, img.height - th - margin * 2

            # 가독성을 위해 옅은 그림자를 먼저 깔고 흰 글씨를 얹는다
            draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 110))
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 190))

            out = Image.alpha_composite(img, layer).convert('RGB')
            out.save(path, quality=92)
        except Exception:
            # 워터마크 실패가 업로드 자체를 막지 않도록 한다
            pass

    # ----- 주차(월~일) 기준 -----

    @staticmethod
    def week_start(moment=None):
        """해당 시각이 속한 주의 월요일 (랭킹과 같은 기준)"""
        tz = timezone.get_current_timezone()
        moment = moment or timezone.now()
        if timezone.is_aware(moment):
            moment = moment.astimezone(tz)
        day = moment.date()
        return day - timedelta(days=day.weekday())

    @staticmethod
    def week_range(start):
        """월요일 날짜 -> (시작 시각, 끝 시각)"""
        tz = timezone.get_current_timezone()
        begin = timezone.make_aware(datetime.combine(start, time.min), tz)
        return begin, begin + timedelta(days=7)

    @classmethod
    def top_of_week(cls, start):
        """그 주에 올라온 글 중 좋아요 1위 (좋아요가 하나도 없으면 없음)"""
        begin, end = cls.week_range(start)
        return (
            cls.objects.filter(
                is_hidden=False, like_count__gt=0,
                created_at__gte=begin, created_at__lt=end,
            )
            .select_related('author')
            .order_by('-like_count', '-created_at')
            .first()
        )

    @classmethod
    def current_top(cls):
        """사이드바·목록 상단에 띄울 1위. 이번 주가 비어 있으면 지난주 우승자"""
        this_week = cls.week_start()
        post = cls.top_of_week(this_week)
        if post:
            return {'post': post, 'label': '이번 주 1위', 'week_start': this_week}
        last_week = this_week - timedelta(days=7)
        post = cls.top_of_week(last_week)
        if post:
            return {'post': post, 'label': '지난주 1위', 'week_start': last_week}
        # 아직 좋아요를 받은 글이 없으면 가장 최근 글을 보여준다
        post = cls.objects.filter(is_hidden=False).select_related('author').order_by('-created_at').first()
        if post:
            return {'post': post, 'label': '새로 올라온 자랑', 'week_start': this_week}
        return {'post': None, 'label': '', 'week_start': this_week}

    @classmethod
    def past_winners(cls, weeks=6):
        """지난 주차별 1위 모음 (이번 주 제외)"""
        this_week = cls.week_start()
        out = []
        for i in range(1, weeks + 1):
            start = this_week - timedelta(days=7 * i)
            post = cls.top_of_week(start)
            if post:
                out.append({'post': post, 'start': start, 'end': start + timedelta(days=6)})
        return out


class BragLike(models.Model):
    """자랑 글 좋아요 - 비회원은 세션 기준"""

    post = models.ForeignKey(
        BragPost, on_delete=models.CASCADE,
        related_name='likes', verbose_name=_('자랑 글')
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='brag_likes',
        verbose_name=_('회원')
    )
    session_key = models.CharField(_('세션 키'), max_length=40, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('자랑 좋아요')
        verbose_name_plural = _('자랑 좋아요')
        constraints = [
            models.UniqueConstraint(
                fields=['post', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_brag_like_user'
            ),
            models.UniqueConstraint(
                fields=['post', 'session_key'],
                condition=models.Q(user__isnull=True),
                name='unique_brag_like_session'
            ),
        ]

    def __str__(self):
        who = self.user.nickname if self.user else f'비회원({self.session_key[:6]})'
        return f'{who} ♥ {self.post_id}'
