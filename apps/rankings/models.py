from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Ranking(models.Model):
    """랭킹"""
    
    class PeriodType(models.TextChoices):
        ALL = 'ALL', _('전체')
        WEEKLY = 'WEEKLY', _('주간')
        MONTHLY = 'MONTHLY', _('월간')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rankings',
        verbose_name=_('사용자')
    )
    period_type = models.CharField(
        _('기간 유형'),
        max_length=10,
        choices=PeriodType.choices
    )
    period_start = models.DateField(
        _('기간 시작일'),
        help_text=_('해당 기간의 시작 날짜')
    )
    
    # 점수 구성 요소 (디버깅 및 상세 표시용)
    approved_posts_count = models.PositiveIntegerField(_('승인된 글 수'), default=0)
    likes_received_count = models.PositiveIntegerField(_('받은 좋아요 수'), default=0)
    valid_received_count = models.PositiveIntegerField(_('받은 VALID 수'), default=0)
    invalid_received_count = models.PositiveIntegerField(_('받은 INVALID 수'), default=0)
    farming_likes_received_count = models.PositiveIntegerField(_('농사 일지 좋아요 수'), default=0)
    copy_received_count = models.PositiveIntegerField(_('받은 복사 수'), default=0)
    
    # 최종 점수 및 순위
    score = models.IntegerField(_('총 점수'), default=0)  # 음수 가능하도록 IntegerField로 변경
    rank = models.PositiveIntegerField(_('순위'), default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('랭킹')
        verbose_name_plural = _('랭킹들')
        unique_together = ['user', 'period_type', 'period_start']
        ordering = ['period_type', 'rank']
        indexes = [
            models.Index(fields=['period_type', 'period_start', 'rank']),
            models.Index(fields=['period_type', 'period_start', '-score']),
        ]
    
    def __str__(self):
        return f"{self.user.nickname} - {self.get_period_type_display()} #{self.rank} ({self.score}점)"
    
    def calculate_score(self):
        """점수 계산"""
        from django.conf import settings
        
        score_config = getattr(settings, 'RANKING_SCORE', {
            'approved_post': 10,
            'like_received': 5,
            'farming_like': 10,
            'copy_received': 2,
        })
        
        self.score = (
            self.approved_posts_count * score_config.get('approved_post', 10) +
            self.likes_received_count * score_config.get('like_received', 5) +
            self.farming_likes_received_count * score_config.get('farming_like', 10) +
            self.copy_received_count * score_config.get('copy_received', 2)
        )
        return self.score
