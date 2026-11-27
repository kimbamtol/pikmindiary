import re

from django.db import models
from django.conf import settings

# 업데이트 내역 한 줄의 생김새: *내용 (26.11.25)
UPDATE_LINE = re.compile(r'^\*(?P<text>.*?)\s*\((?P<y>\d\d)\.(?P<m>\d\d)\.(?P<d>\d\d)\)\s*$')

# 이 말이 들어 있으면 「고침」으로 본다. 나머지는 새 기능이다.
# '수정' 하나만 보면 안 된다 - 「글 수정 시에도 ... 버튼 추가」 같은
# 새 기능까지 고침으로 끌려온다. 고친 글은 늘 '문제' 나 '고쳤' 을 쓴다.
FIX_WORDS = ('문제', '고쳤', '고침')


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

    def update_groups(self):
        """업데이트 내역을 달 > 날짜 > 줄 로 묶어 돌려준다. 최신이 앞이다.

        예전에는 41줄을 통째로 쏟아놔서 읽을 수가 없었다. 달 버튼을 누르면
        그 달만 보이게 하려고 여기서 묶는다.

        날짜를 못 읽은 줄은 버리지 않는다. 맨 뒤 「기타」로 모아서 어쨌든
        화면에 나오게 한다 - 관리자가 형식을 조금 어긋나게 적었다고 해서
        공지가 조용히 사라지면 알아차릴 방법이 없다.
        """
        months, odd = [], []
        index = {}

        for raw in self.update_log.splitlines():
            raw = raw.strip()
            if not raw:
                continue

            m = UPDATE_LINE.match(raw)
            if not m:
                odd.append(raw.lstrip('*').strip())
                continue

            y, mm, dd = m.group('y'), m.group('m'), m.group('d')
            text = m.group('text')
            item = {'text': text, 'fix': any(w in text for w in FIX_WORDS)}

            month = index.get((y, mm))
            if month is None:
                month = {
                    'key': 'u%s%s' % (y, mm),
                    'year': '20' + y,
                    'label': '%d월' % int(mm),
                    'days': [],
                    '_days': {},
                }
                index[(y, mm)] = month
                months.append(month)

            day = month['_days'].get(dd)
            if day is None:
                day = {'label': '%d월 %d일' % (int(mm), int(dd)), 'items': []}
                month['_days'][dd] = day
                month['days'].append(day)
            day['items'].append(item)

        # 적은 순서가 오래된 것부터라 뒤집는다. 날짜와 줄도 같이 뒤집는다.
        months.reverse()
        for month in months:
            month.pop('_days')
            month['days'].reverse()
            for day in month['days']:
                day['items'].reverse()

        if odd:
            months.append({
                'key': 'uodd', 'year': '', 'label': '기타',
                'days': [{'label': '날짜를 읽지 못한 줄',
                          'items': [{'text': t, 'fix': False} for t in odd]}],
            })
        return months


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

    # 새 디자인 체험 (수첩)
    design_beta_enabled = models.BooleanField(
        '새 디자인 체험 공개',
        default=False,
        help_text='켜면 유저에게 새 디자인 안내 팝업과 전환 버튼이 보입니다.'
    )
    design_beta_popup_enabled = models.BooleanField(
        '새 디자인 안내 팝업',
        default=True,
        help_text='좌표 목록 첫 진입 시 안내 팝업을 띄웁니다. (체험 공개가 켜져 있을 때만 동작)'
    )
    
    # 엽서 변경(너프) 자동 표시
    nerf_threshold = models.PositiveIntegerField(
        '너프 표시 기준 인원',
        default=3,
        help_text='정해진 기간 안에 이 인원 이상이 제보하면 제목 앞에 [너프됨]이 붙습니다.'
    )
    nerf_window_days = models.PositiveIntegerField(
        '너프 집계 기간(일)',
        default=7,
        help_text='최근 며칠간의 제보를 셀지 정합니다.'
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


class DesignVote(models.Model):
    """새 디자인(수첩) 체험 투표 - 비회원 포함 1인 1표"""

    class Choice(models.TextChoices):
        NEW = 'NEW', '새 디자인이 좋다'
        OLD = 'OLD', '예전이 낫다'

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='design_votes',
        verbose_name='회원'
    )
    session_key = models.CharField('세션 키', max_length=40, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)

    choice = models.CharField('선택', max_length=3, choices=Choice.choices)
    comment = models.CharField('한마디', max_length=200, blank=True)

    created_at = models.DateTimeField('첫 투표일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '디자인 투표'
        verbose_name_plural = '디자인 투표'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(user__isnull=False),
                name='unique_design_vote_per_user'
            ),
            models.UniqueConstraint(
                fields=['session_key'],
                condition=models.Q(user__isnull=True),
                name='unique_design_vote_per_session'
            ),
        ]

    def __str__(self):
        who = self.user.nickname if self.user else f'비회원({self.session_key[:6]})'
        return f'{who} - {self.get_choice_display()}'

    @classmethod
    def tally(cls):
        """집계 결과"""
        new = cls.objects.filter(choice=cls.Choice.NEW).count()
        old = cls.objects.filter(choice=cls.Choice.OLD).count()
        total = new + old
        return {
            'new': new,
            'old': old,
            'total': total,
            'new_pct': round(new / total * 100) if total else 0,
            'old_pct': round(old / total * 100) if total else 0,
        }
