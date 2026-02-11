from django.db import models
from django.conf import settings


class FarmingJournal(models.Model):
    """농사 일지 - 본인이 한 농사 기록 공유"""
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farming_journals',
        null=True,
        blank=True
    )
    # 비회원 지원
    guest_nickname = models.CharField(max_length=50, blank=True, verbose_name='게스트 닉네임')
    guest_password = models.CharField(max_length=128, blank=True, verbose_name='게스트 비밀번호')
    title = models.CharField(max_length=200, verbose_name='제목')
    content = models.TextField(verbose_name='내용')
    
    # 좌표 정보
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True,
        verbose_name='위도'
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        null=True, blank=True,
        verbose_name='경도'
    )
    location_name = models.CharField(max_length=200, blank=True, verbose_name='장소명')
    
    # 농사 정보
    flower_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='꽃 종류',
        help_text='예: 빨간 꽃, 노란 꽃, 파란 꽃 등'
    )
    flower_count = models.PositiveIntegerField(default=0, verbose_name='심은 꽃 수')
    
    # 이미지
    image = models.ImageField(upload_to='farming/journals/', blank=True, null=True)
    
    # 좋아요 카운트
    like_count = models.PositiveIntegerField(default=0, verbose_name='좋아요 수')
    
    # 댓글 카운트
    comment_count = models.PositiveIntegerField(default=0, verbose_name='댓글 수')
    
    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '농사 일지'
        verbose_name_plural = '농사 일지'
    
    def __str__(self):
        return self.title


class FarmingJournalLike(models.Model):
    """농사 일지 좋아요"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farming_journal_likes',
        verbose_name='사용자'
    )
    journal = models.ForeignKey(
        FarmingJournal,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name='농사 일지'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = '농사 일지 좋아요'
        verbose_name_plural = '농사 일지 좋아요'
        unique_together = ['user', 'journal']
        indexes = [
            models.Index(fields=['user', 'journal']),
            models.Index(fields=['journal', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user} ❤️ {self.journal.title}"


class FarmingRequest(models.Model):
    """농사 요청 - 도움 요청"""
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farming_requests',
        null=True,
        blank=True
    )
    # 비회원 지원
    guest_nickname = models.CharField(max_length=50, blank=True, verbose_name='게스트 닉네임')
    guest_password = models.CharField(max_length=128, blank=True, verbose_name='게스트 비밀번호')
    title = models.CharField(max_length=200, verbose_name='제목')
    content = models.TextField(verbose_name='설명')
    
    # 좌표 정보 (필수)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        verbose_name='위도'
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7,
        verbose_name='경도'
    )
    location_name = models.CharField(max_length=200, verbose_name='장소명')
    
    # 필요한 꽃 정보
    flower_type = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='필요한 꽃',
        help_text='예: 빨간 꽃, 아무 꽃이나 등'
    )
    
    # 마감 시간
    deadline = models.DateTimeField(null=True, blank=True, verbose_name='마감 시간')
    
    # 상태
    STATUS_CHOICES = [
        ('open', '모집중'),
        ('in_progress', '진행중'),
        ('completed', '완료'),
        ('closed', '마감'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='상태'
    )
    
    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '농사 요청'
        verbose_name_plural = '농사 요청'
    
    def __str__(self):
        return self.title


class FarmingParticipation(models.Model):
    """농사 참여 기록"""
    request = models.ForeignKey(
        FarmingRequest,
        on_delete=models.CASCADE,
        related_name='participations'
    )
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='farming_participations'
    )
    message = models.TextField(blank=True, verbose_name='메시지')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['request', 'participant']
        ordering = ['-created_at']
        verbose_name = '농사 참여'
        verbose_name_plural = '농사 참여'
    
    def __str__(self):
        return f"{self.participant} -> {self.request}"
