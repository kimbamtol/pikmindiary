from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    """
    확장 사용자 모델
    - Google 로그인 사용자
    - 비회원 (닉네임 + 비밀번호로 글 작성)
    """
    nickname = models.CharField(
        _('닉네임'),
        max_length=30,
        unique=True,
        help_text=_('다른 사용자에게 표시되는 이름입니다.')
    )
    is_guest = models.BooleanField(
        _('비회원 여부'),
        default=False,
        help_text=_('비회원으로 작성한 경우 True')
    )
    guest_password = models.CharField(
        _('비회원 비밀번호'),
        max_length=128,
        blank=True,
        help_text=_('비회원이 글 수정/삭제 시 사용하는 비밀번호 (해시됨)')
    )
    
    # 프로필 관련
    profile_image = models.ImageField(
        _('프로필 이미지'),
        upload_to='profiles/',
        blank=True,
        null=True
    )
    bio = models.TextField(
        _('자기소개'),
        max_length=200,
        blank=True
    )
    profile_emoji = models.CharField(
        _('프로필 이모지'),
        max_length=10,
        blank=True,
        default='',
        help_text=_('피크민 관련 이모지 (랭킹 등록 사용자만)')
    )

    # 특별 칭호 (관리자 부여 또는 랭커 선택)
    class SpecialTitle(models.TextChoices):
        NONE = '', _('없음')
        COORDINATOR = 'coordinator', _('좌표 마스터')
        EXPLORER = 'explorer', _('피크민 탐험가')
        PIONEER = 'pioneer', _('개척자')
        LEGEND = 'legend', _('전설의 대원')
        SUPPORTER = 'supporter', _('서포터')

    # 1위만 선택 가능한 프리미엄 칭호
    PREMIUM_TITLES = ['explorer', 'legend', 'coordinator']
    # 2~3위도 선택 가능한 일반 칭호
    NORMAL_TITLES = ['pioneer', 'supporter']

    special_title = models.CharField(
        _('특별 칭호'),
        max_length=20,
        choices=SpecialTitle.choices,
        default=SpecialTitle.NONE,
        blank=True,
        help_text=_('관리자가 부여하는 특별 칭호')
    )

    # 랭커가 직접 선택한 칭호 (관리자 부여 칭호보다 우선순위 낮음)
    selected_title = models.CharField(
        _('선택한 칭호'),
        max_length=20,
        choices=SpecialTitle.choices,
        default=SpecialTitle.NONE,
        blank=True,
        help_text=_('랭커가 직접 선택한 칭호 (1위: 모든 칭호, 2~3위: 일반 칭호만)')
    )

    # 배지 스타일 선택
    class BadgeStyle(models.TextChoices):
        DEFAULT = 'default', _('기본')
        BACKGROUND_ONLY = 'background', _('배경만')
        GLOW = 'glow', _('글로우 효과')
        UNDERLINE = 'underline', _('홀로그램 언더라인')

    # 전용 아이템 코드 목록 (관리자가 exclusive_perks로 개별 허용)
    EXCLUSIVE_STYLE_CODES = {'underline'}
    EXCLUSIVE_COLOR_CODES = {'rainbow'}
    EXCLUSIVE_TITLE_CODES = {'explorer'}

    # 전용 아이템 (관리자가 DB에서 관리, 쉼표 구분: "underline,rainbow,explorer")
    exclusive_perks = models.CharField(
        _('전용 아이템'),
        max_length=200,
        blank=True,
        default='',
        help_text=_('전용 스타일/색상/칭호 코드 (쉼표 구분, 예: underline,rainbow,explorer)')
    )

    badge_style = models.CharField(
        _('배지 스타일'),
        max_length=20,
        choices=BadgeStyle.choices,
        default=BadgeStyle.DEFAULT,
        blank=True,
        help_text=_('닉네임 배지의 CSS 스타일')
    )

    # 닉네임/칭호 색상 선택
    class ColorChoice(models.TextChoices):
        DEFAULT = '', _('기본')
        RED = 'red', _('빨강')
        ORANGE = 'orange', _('주황')
        YELLOW = 'yellow', _('노랑')
        GREEN = 'green', _('초록')
        BLUE = 'blue', _('파랑')
        PURPLE = 'purple', _('보라')
        PINK = 'pink', _('분홍')
        RAINBOW = 'rainbow', _('무지개')

    nickname_color = models.CharField(
        _('닉네임 색상'),
        max_length=20,
        choices=ColorChoice.choices,
        default=ColorChoice.DEFAULT,
        blank=True
    )

    title_color = models.CharField(
        _('칭호 글자 색상'),
        max_length=20,
        choices=ColorChoice.choices,
        default=ColorChoice.DEFAULT,
        blank=True
    )

    title_bg_color = models.CharField(
        _('칭호 배경 색상'),
        max_length=20,
        choices=ColorChoice.choices,
        default=ColorChoice.DEFAULT,
        blank=True
    )

    nickname_bg_color = models.CharField(
        _('닉네임 배경 색상'),
        max_length=20,
        choices=ColorChoice.choices,
        default=ColorChoice.DEFAULT,
        blank=True
    )

    # 통계 (캐시용)
    total_posts = models.PositiveIntegerField(default=0)
    total_likes_received = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('사용자')
        verbose_name_plural = _('사용자들')
        
    def __str__(self):
        return self.nickname or self.username
    
    def save(self, *args, **kwargs):
        # 닉네임이 없으면 username 사용
        if not self.nickname:
            self.nickname = self.username or f'user_{self.pk}'
        super().save(*args, **kwargs)

    def get_ranking_position(self):
        """현재 사용자의 랭킹 순위 반환 (1, 2, 3 또는 None)"""
        try:
            from apps.rankings.models import Ranking
            # 전체 기간(ALL) 랭킹에서 상위 3명 조회
            top_3_rankings = Ranking.objects.filter(
                period_type=Ranking.PeriodType.ALL
            ).order_by('-score')[:3]

            for idx, ranking in enumerate(top_3_rankings, 1):
                if ranking.user_id == self.id:
                    return idx
        except Exception:
            pass
        return None

    def get_active_title(self):
        """현재 적용될 칭호 반환 (관리자 부여 > 선택한 칭호)"""
        if self.special_title:
            return self.special_title
        if self.selected_title:
            return self.selected_title
        return ''

    def get_badge_class(self):
        """랭킹 순위 또는 특별 칭호에 따른 CSS 클래스 반환"""
        active_title = self.get_active_title()
        # 칭호가 있으면 우선
        if active_title:
            return f'badge-special badge-{active_title}'
        # 랭킹 순위
        position = self.get_ranking_position()
        if position == 1:
            return 'badge-gold'
        elif position == 2:
            return 'badge-silver'
        elif position == 3:
            return 'badge-bronze'
        return ''

    def is_admin_user(self):
        """관리자 여부 확인"""
        return self.is_staff

    def _get_perks_set(self):
        """exclusive_perks 필드를 set으로 반환"""
        if not self.exclusive_perks:
            return set()
        return {p.strip() for p in self.exclusive_perks.split(',') if p.strip()}

    def _has_perk(self, code):
        """전용 아이템 보유 여부"""
        return code in self._get_perks_set()

    def get_available_titles(self):
        """랭킹 순위에 따라 선택 가능한 칭호 목록 반환"""
        title_choices = dict(self.SpecialTitle.choices)

        if self.is_admin_user():
            available = self.PREMIUM_TITLES + self.NORMAL_TITLES
            return [(code, title_choices.get(code, code))
                    for code in available]

        position = self.get_ranking_position()
        if position is None:
            return []

        if position == 1:
            available = self.PREMIUM_TITLES + self.NORMAL_TITLES
        else:
            available = self.NORMAL_TITLES

        # 전용 칭호는 perk 보유 시에만 포함
        return [(code, title_choices.get(code, code))
                for code in available
                if code not in self.EXCLUSIVE_TITLE_CODES or self._has_perk(code)]

    def can_select_title(self, title_code):
        """해당 칭호를 선택할 수 있는지 확인"""
        if self.is_admin_user():
            return True
        # 전용 칭호는 perk 필요
        if title_code in self.EXCLUSIVE_TITLE_CODES and not self._has_perk(title_code):
            return False
        position = self.get_ranking_position()
        if position is None:
            return False
        if position == 1:
            return True
        return title_code in self.NORMAL_TITLES

    def can_customize_badge(self):
        """배지 커스터마이즈 가능 여부"""
        return self.is_admin_user() or self.get_ranking_position() is not None

    def can_use_style(self, style_code):
        """해당 스타일을 사용할 수 있는지 확인"""
        if self.is_admin_user():
            return True
        if style_code in self.EXCLUSIVE_STYLE_CODES:
            return self._has_perk(style_code)
        return self.can_customize_badge()

    def get_available_styles(self):
        """사용 가능한 스타일 목록 반환"""
        if self.is_admin_user():
            return list(self.BadgeStyle.choices)
        return [(code, label) for code, label in self.BadgeStyle.choices
                if code not in self.EXCLUSIVE_STYLE_CODES or self._has_perk(code)]

    def can_use_color(self, color_code):
        """해당 색상을 사용할 수 있는지 확인"""
        if self.is_admin_user():
            return True
        if color_code in self.EXCLUSIVE_COLOR_CODES:
            return self._has_perk(color_code)
        return self.can_customize_badge()

    def get_available_colors(self):
        """사용 가능한 색상 목록 반환"""
        if self.is_admin_user():
            return list(self.ColorChoice.choices)
        return [(code, label) for code, label in self.ColorChoice.choices
                if code not in self.EXCLUSIVE_COLOR_CODES or self._has_perk(code)]

    def get_special_title_display_with_icon(self):
        """특별 칭호 반환 (아이콘 제거됨)"""
        if self.special_title:
            return self.get_special_title_display()
        return ''

    def has_ranking(self):
        """랭킹에 등록되어 있는지 확인"""
        try:
            from apps.rankings.models import Ranking
            return Ranking.objects.filter(
                user=self,
                period_type=Ranking.PeriodType.ALL
            ).exists()
        except Exception:
            return False


class UserBan(models.Model):
    """사용자/IP 정지 모델"""
    
    class BanDuration(models.TextChoices):
        ONE_DAY = '1d', _('1일')
        THREE_DAYS = '3d', _('3일')
        ONE_WEEK = '7d', _('7일')
        ONE_MONTH = '30d', _('1개월')
        ONE_YEAR = '365d', _('1년')
        PERMANENT = 'perm', _('영구')
    
    # 정지 대상 (둘 중 하나 또는 둘 다)
    user = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bans',
        verbose_name=_('정지된 사용자')
    )
    ip_address = models.GenericIPAddressField(
        _('IP 주소'),
        null=True,
        blank=True
    )
    
    # 정지 정보
    duration = models.CharField(
        _('정지 기간'),
        max_length=10,
        choices=BanDuration.choices,
        default=BanDuration.ONE_DAY
    )
    reason = models.TextField(
        _('정지 사유'),
        blank=True
    )
    
    # 시간 정보
    banned_at = models.DateTimeField(_('정지 시작'), auto_now_add=True)
    expires_at = models.DateTimeField(_('정지 만료'), null=True, blank=True)
    
    # 정지한 관리자
    banned_by = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        related_name='bans_issued',
        verbose_name=_('정지한 관리자')
    )
    
    # 정지 해제 여부
    is_active = models.BooleanField(_('활성 상태'), default=True)
    unbanned_at = models.DateTimeField(_('정지 해제 시간'), null=True, blank=True)
    unbanned_by = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bans_lifted',
        verbose_name=_('정지 해제한 관리자')
    )
    
    class Meta:
        verbose_name = _('정지')
        verbose_name_plural = _('정지 목록')
        ordering = ['-banned_at']
    
    def __str__(self):
        target = self.user.nickname if self.user else self.ip_address
        return f"{target} - {self.get_duration_display()}"
    
    def save(self, *args, **kwargs):
        # 정지 만료 시간 계산
        if not self.expires_at and self.duration != self.BanDuration.PERMANENT:
            from django.utils import timezone
            from datetime import timedelta
            
            duration_map = {
                '1d': timedelta(days=1),
                '3d': timedelta(days=3),
                '7d': timedelta(days=7),
                '30d': timedelta(days=30),
                '365d': timedelta(days=365),
            }
            if self.duration in duration_map:
                self.expires_at = timezone.now() + duration_map[self.duration]
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """정지가 만료되었는지 확인"""
        if self.duration == self.BanDuration.PERMANENT:
            return False
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False
    
    @classmethod
    def is_user_banned(cls, user):
        """사용자가 정지되었는지 확인"""
        from django.utils import timezone
        return cls.objects.filter(
            user=user,
            is_active=True
        ).filter(
            models.Q(duration='perm') | models.Q(expires_at__gt=timezone.now())
        ).exists()
    
    @classmethod
    def is_ip_banned(cls, ip_address):
        """IP가 정지되었는지 확인"""
        from django.utils import timezone
        return cls.objects.filter(
            ip_address=ip_address,
            is_active=True
        ).filter(
            models.Q(duration='perm') | models.Q(expires_at__gt=timezone.now())
        ).exists()
