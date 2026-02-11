from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


class Coordinate(models.Model):
    """좌표 게시글"""
    
    class Category(models.TextChoices):
        MUSHROOM = 'MUSHROOM', _('버섯')
        BIGFLOWER = 'BIGFLOWER', _('빅플라워')
        SEEDLING = 'SEEDLING', _('모종')
        OTHER = 'OTHER', _('기타')
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('대기')
        APPROVED = 'APPROVED', _('승인')
        REJECTED = 'REJECTED', _('거절')
    
    class Region(models.TextChoices):
        KOREA = 'KOREA', _('한국 🇰🇷')
        JAPAN = 'JAPAN', _('일본 🇯🇵')
        NORTH_AMERICA = 'NORTH_AMERICA', _('북미 🌎')
        EUROPE = 'EUROPE', _('유럽 🇪🇺')
        ASIA_OTHER = 'ASIA_OTHER', _('아시아 🌏')
        OTHER = 'OTHER', _('기타 🌍')
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='coordinates',
        verbose_name=_('작성자')
    )
    
    title = models.CharField(_('제목'), max_length=100)
    postcard_name = models.CharField(_('엽서이름'), max_length=100, blank=True)
    description = models.TextField(_('설명'), blank=True)
    
    # 위치 정보
    latitude = models.DecimalField(
        _('위도'),
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        _('경도'),
        max_digits=10,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    
    # 분류
    category = models.CharField(
        _('카테고리'),
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )
    status = models.CharField(
        _('상태'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    region = models.CharField(
        _('지역'),
        max_length=20,
        choices=Region.choices,
        default=Region.OTHER,
        blank=True
    )
    
    # 집계 필드 (성능 최적화용 - 별도 쿼리 없이 정렬/필터 가능)
    like_count = models.PositiveIntegerField(_('좋아요 수'), default=0)
    view_count = models.PositiveIntegerField(_('조회수'), default=0)
    bookmark_count = models.PositiveIntegerField(_('북마크 수'), default=0)
    comment_count = models.PositiveIntegerField(_('댓글 수'), default=0)
    valid_count = models.PositiveIntegerField(_('유효 평가 수'), default=0)
    invalid_count = models.PositiveIntegerField(_('무효 평가 수'), default=0)
    copy_count = models.PositiveIntegerField(_('복사 수'), default=0)
    
    # 타임스탬프
    created_at = models.DateTimeField(_('작성일'), auto_now_add=True)
    updated_at = models.DateTimeField(_('수정일'), auto_now=True)
    approved_at = models.DateTimeField(_('승인일'), null=True, blank=True)
    last_verified_at = models.DateTimeField(_('마지막 검증일'), null=True, blank=True)
    
    # 비회원 작성용 비밀번호
    guest_password = models.CharField(
        _('비회원 비밀번호'),
        max_length=128,
        blank=True,
        help_text=_('비회원이 글 수정/삭제 시 사용')
    )

    # 워터마크 옵션
    watermark_enabled = models.BooleanField(
        _('워터마크 표시'),
        default=False,
        help_text=_('사진에 닉네임 워터마크 표시')
    )
    watermark_name = models.CharField(
        _('워터마크 닉네임'),
        max_length=50,
        blank=True,
        help_text=_('워터마크에 표시될 이름 (비어있으면 작성자 닉네임 사용)')
    )
    
    class Meta:
        verbose_name = _('좌표')
        verbose_name_plural = _('좌표들')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['-like_count']),
            models.Index(fields=['-valid_count']),
            models.Index(fields=['author', 'status']),
        ]
    
    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"
    
    @property
    def trust_score(self):
        """신뢰도 점수 (valid - invalid)"""
        return self.valid_count - self.invalid_count
    
    @property
    def is_trusted(self):
        """신뢰할 수 있는 좌표인지"""
        return self.trust_score >= 0 and self.valid_count >= 3
    
    @property
    def is_outdated(self):
        """오래된 좌표인지 (30일 이상 검증 없음)"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.last_verified_at:
            # 승인 후 30일 이상 검증 없음
            if self.approved_at:
                return timezone.now() - self.approved_at > timedelta(days=30)
            return False
        return timezone.now() - self.last_verified_at > timedelta(days=30)
    
    def get_coords_string(self):
        """좌표 문자열 반환 (복사용)"""
        return f"{self.latitude}, {self.longitude}"
    
    def detect_region(self):
        """위도/경도로 지역 자동 감지"""
        lat = float(self.latitude)
        lon = float(self.longitude)
        
        # 한국: 위도 33~38.5, 경도 124~130
        if 33 <= lat <= 38.5 and 124 <= lon <= 130:
            return self.Region.KOREA
        
        # 일본: 위도 24~46, 경도 123~154 (한국 제외)
        if 24 <= lat <= 46 and 123 <= lon <= 154:
            return self.Region.JAPAN
        
        # 북미: 위도 15~72, 경도 -170~-50
        if 15 <= lat <= 72 and -170 <= lon <= -50:
            return self.Region.NORTH_AMERICA
        
        # 유럽: 위도 35~72, 경도 -25~60
        if 35 <= lat <= 72 and -25 <= lon <= 60:
            return self.Region.EUROPE
        
        # 아시아 기타: 위도 -10~55, 경도 60~150 (한국/일본 제외)
        if -10 <= lat <= 55 and 60 <= lon <= 150:
            return self.Region.ASIA_OTHER
        
        return self.Region.OTHER
    
    def save(self, *args, **kwargs):
        """저장 시 지역 자동 감지"""
        if not self.region or self.region == self.Region.OTHER:
            self.region = self.detect_region()
        super().save(*args, **kwargs)


class CoordinateImage(models.Model):
    """좌표 게시글 이미지"""

    coordinate = models.ForeignKey(
        Coordinate,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('좌표')
    )
    image = models.ImageField(
        _('이미지'),
        upload_to='coordinates/%Y/%m/'
    )
    order = models.PositiveSmallIntegerField(_('순서'), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('좌표 이미지')
        verbose_name_plural = _('좌표 이미지들')
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.coordinate.title} - 이미지 {self.order + 1}"

    def save(self, *args, **kwargs):
        """저장 시 워터마크 적용"""
        super().save(*args, **kwargs)

        # 워터마크 적용
        if self.coordinate.watermark_enabled and self.image:
            self._apply_watermark()

    def _apply_watermark(self):
        """이미지에 워터마크 적용"""
        from PIL import Image, ImageDraw, ImageFont
        import os

        try:
            img_path = self.image.path
            img = Image.open(img_path)

            # RGBA로 변환 (투명도 지원)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # 워터마크 텍스트 결정
            watermark_text = self.coordinate.watermark_name
            if not watermark_text:
                if self.coordinate.author:
                    watermark_text = self.coordinate.author.nickname
                else:
                    watermark_text = "피크민다이어리"

            # 워터마크 레이어 생성
            txt_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)

            # 폰트 크기 계산 (이미지 너비의 5% - 더 굵직하게)
            font_size = max(24, int(img.width * 0.05))

            # 시스템 폰트 사용 (한글 지원 - Bold 폰트 우선)
            try:
                # 우분투/데비안 한글 Bold 폰트
                font = ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf', font_size)
            except OSError:
                try:
                    # 일반 나눔고딕
                    font = ImageFont.truetype('/usr/share/fonts/truetype/nanum/NanumGothic.ttf', font_size)
                except OSError:
                    try:
                        # 대체 폰트
                        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
                    except OSError:
                        font = ImageFont.load_default()

            # 텍스트 크기 계산
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # 워터마크 위치 계산 (중앙 영역 대각선 배치)
            # 이미지 중앙에서 좌상단, 우하단으로 대각선 배치
            center_x = img.width // 2
            center_y = img.height // 2
            offset = int(min(img.width, img.height) * 0.15)  # 중앙에서 15% 떨어진 위치

            positions = [
                # 중앙-좌상단
                (center_x - offset - text_width // 2, center_y - offset - text_height // 2),
                # 중앙-우하단
                (center_x + offset - text_width // 2, center_y + offset - text_height // 2),
            ]

            # 더 연한 반투명 텍스트 (투명도 낮춤)
            outline_color = (0, 0, 0, 40)  # 테두리 더 연하게
            text_color = (255, 255, 255, 80)  # 텍스트 더 연하게

            for x, y in positions:
                # 테두리 (연한 검은색)
                for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]:
                    draw.text((x + dx, y + dy), watermark_text, font=font, fill=outline_color)
                # 메인 텍스트 (연한 반투명 흰색)
                draw.text((x, y), watermark_text, font=font, fill=text_color)

            # 레이어 합성
            watermarked = Image.alpha_composite(img, txt_layer)

            # RGB로 변환 후 저장 (JPEG 호환)
            watermarked = watermarked.convert('RGB')
            watermarked.save(img_path, quality=90, optimize=True)

        except Exception as e:
            # 워터마크 실패해도 이미지는 유지
            import logging
            logging.error(f"워터마크 적용 실패: {e}")
