from django.db import models
from django.conf import settings


class SiteNotice(models.Model):
    """관리자가 수정할 수 있는 사이트 공지/메시지"""
    LOCATION_CHOICES = [
        ('coordinates_list', '좌표 목록 페이지'),
        ('landing', '메인 페이지'),
        ('farming_list', '농사 일지 페이지'),
    ]
    
    location = models.CharField(
        '표시 위치',
        max_length=50,
        choices=LOCATION_CHOICES,
        unique=True
    )
    title = models.CharField('제목', max_length=100, blank=True)
    content = models.TextField('내용', help_text='사이트 공지 내용')
    update_log = models.TextField('업데이트 내역', blank=True, help_text='사이트 업데이트 내역')
    is_active = models.BooleanField('활성화', default=True)
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)
    
    class Meta:
        verbose_name = '사이트 공지'
        verbose_name_plural = '사이트 공지'
    
    def __str__(self):
        return f"[{self.get_location_display()}] {self.title or '공지'}"


class Suggestion(models.Model):
    """운영자에게 건의하기"""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기중'
        REVIEWED = 'REVIEWED', '검토완료'
        RESOLVED = 'RESOLVED', '처리완료'
    
    class Category(models.TextChoices):
        BUG = 'BUG', '버그 신고'
        FEATURE = 'FEATURE', '기능 제안'
        QUESTION = 'QUESTION', '문의'
        OTHER = 'OTHER', '기타'
    
    # 회원인 경우
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suggestions',
        verbose_name='작성자'
    )
    # 비회원인 경우
    guest_nickname = models.CharField('닉네임(비회원)', max_length=50, blank=True)
    email = models.EmailField('이메일(선택)', blank=True)
    
    category = models.CharField(
        '분류',
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )
    title = models.CharField('제목', max_length=100)
    content = models.TextField('내용')
    
    status = models.CharField(
        '상태',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    admin_note = models.TextField('관리자 메모', blank=True, help_text='내부용 메모 (사용자에게 보이지 않음)')
    admin_reply = models.TextField('관리자 답변', blank=True, help_text='사용자에게 표시되는 공식 답변')
    replied_at = models.DateTimeField('답변일', null=True, blank=True)
    
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)
    
    class Meta:
        verbose_name = '건의사항'
        verbose_name_plural = '건의사항'
        ordering = ['-created_at']
    
    def __str__(self):
        name = self.author.nickname if self.author else self.guest_nickname
        return f"[{self.get_category_display()}] {self.title} - {name}"
    
    @property
    def writer_name(self):
        """작성자 이름 반환"""
        if self.author:
            return self.author.nickname
        return self.guest_nickname or '익명'


class SiteSettings(models.Model):
    """사이트 전역 설정 (싱글톤)"""
    
    # 랭커 업로드 제한 해제 설정
    ranker_limit_exempt_rank = models.PositiveIntegerField(
        '랭커 제한 해제 순위',
        default=10,
        help_text='전체 랭킹에서 이 순위 이내의 유저는 일일 업로드 제한이 없습니다. (0 = 비활성화)'
    )
    
    # 일일 업로드 제한
    daily_upload_limit = models.PositiveIntegerField(
        '일일 업로드 제한',
        default=3,
        help_text='카테고리별 하루 업로드 제한 (0 = 무제한)'
    )
    
    updated_at = models.DateTimeField('수정일', auto_now=True)
    
    class Meta:
        verbose_name = '사이트 설정'
        verbose_name_plural = '사이트 설정'
    
    def __str__(self):
        return '사이트 설정'
    
    def save(self, *args, **kwargs):
        # 싱글톤: 항상 pk=1만 허용
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """설정 가져오기 (없으면 생성)"""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
