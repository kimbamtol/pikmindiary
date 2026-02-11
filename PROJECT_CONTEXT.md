# Pikmin Diary - Project Context

> **Site**: https://pikmindiary.com
> **Last Updated**: 2026-02-03

---

## Overview

Pikmin Diary는 Pikmin Bloom 게임 커뮤니티를 위한 위치 정보 및 파밍 활동 공유 플랫폼입니다.

### Core Features
- 게임 내 자원(버섯, 큰꽃, 묘목) 위치 정보 공유
- 파밍 활동 조율 및 커뮤니티 소통
- 사용자 참여 기반 랭킹 시스템

---

## Tech Stack

| Category | Technology |
|----------|------------|
| Backend | Python 3.12, Django 6.0 |
| Database | SQLite (dev), PostgreSQL (prod) |
| Frontend | HTML/CSS/JS, HTMX 1.27.0 |
| Auth | django-allauth (Google OAuth) |
| Image | Pillow 12.0.0 |
| Deploy | Nginx + Gunicorn + Systemd |

---

## Project Structure

```
pikmin-diary/
├── apps/                    # Django apps (9개)
│   ├── accounts/            # 사용자 인증 및 프로필
│   ├── coordinates/         # 위치 공유 (핵심 기능)
│   ├── farming/             # 파밍 일지 및 요청
│   ├── comments/            # 댓글 시스템
│   ├── interactions/        # 좋아요, 북마크, 알림
│   ├── rankings/            # 랭킹 시스템
│   ├── reports/             # 신고 및 모더레이션
│   ├── admin_panel/         # 관리자 대시보드
│   └── core/                # 랜딩, 가이드, 사이트 설정
├── config/                  # Django 설정
├── templates/               # HTML 템플릿
├── static/                  # CSS, JS, images
├── media/                   # 사용자 업로드 파일
├── CLAUDE.md               # Claude 작업 지침
└── PROJECT_CONTEXT.md      # 이 문서
```

---

## Data Models

### accounts (사용자)
- **CustomUser**: 닉네임, 프로필 이미지, 랭킹 이모지, 통계
- **UserBan**: 사용자/IP 차단

### coordinates (위치 공유)
- **Coordinate**: 좌표 게시글
  - Category: MUSHROOM, BIGFLOWER, SEEDLING, OTHER
  - Status: PENDING, APPROVED, REJECTED
  - Region: KOREA, JAPAN, NORTH_AMERICA, EUROPE, ASIA_OTHER, OTHER (자동 감지)
  - 집계 필드: like_count, view_count, comment_count, valid_count, invalid_count, copy_count
  - 워터마크: watermark_enabled, watermark_name (좌상단/우하단 대각선 배치)
- **CoordinateImage**: 게시글 이미지 (워터마크 자동 적용)

### farming (파밍)
- **FarmingJournal**: 파밍 일지
- **FarmingRequest**: 파밍 도움 요청

### comments (댓글)
- **Comment**: 댓글 (대댓글 지원, 사진 첨부 가능)
  - photo 필드로 엽서 자랑 기능

### interactions (상호작용)
- **Like**: 좌표 좋아요
- **CommentLike**: 댓글 좋아요
- **Bookmark**: 북마크
- **ValidityFeedback**: 유효성 평가 (VALID/INVALID)
- **Notification**: 알림 (LIKE, COMMENT, COPY_MILESTONE, SUGGESTION_REPLY)

### rankings (랭킹)
- **Ranking**: 점수 기반 랭킹
  - 승인된 게시물: +10점
  - 받은 좋아요: +2점
  - 유효 피드백: +3점
  - 파밍 좋아요: +10점

### core (사이트 관리)
- **SiteNotice**: 사이트 공지 (content, update_log)
- **Suggestion**: 건의사항
- **SiteSettings**: 전역 설정 (싱글톤)

### reports (신고)
- **Report**: 신고 (SPAM, WRONG_INFO, INAPPROPRIATE, OTHER)

---

## URL Structure

| Path | App | Description |
|------|-----|-------------|
| `/` | core | 랜딩 페이지 |
| `/coordinates/` | coordinates | 좌표 목록/상세/등록 |
| `/farming/` | farming | 파밍 일지/요청 |
| `/accounts/` | accounts | 프로필/설정 |
| `/rankings/` | rankings | 랭킹 보드 |
| `/interactions/` | interactions | AJAX 엔드포인트 |
| `/comments/` | comments | 댓글 CRUD |
| `/reports/` | reports | 신고 |
| `/guide/` | core | 가이드 |
| `/suggestions/` | core | 건의사항 |

---

## Key Implementation Patterns

### 1. Guest Support
비회원도 좌표 등록, 댓글, 좋아요 가능
- DB 저장: 회원은 user FK, 비회원은 guest_nickname + guest_password
- 세션 기반: 비회원 좋아요는 세션에 저장

### 2. Count Caching
집계 필드를 모델에 저장하여 쿼리 최적화
```python
coordinate.like_count = Like.objects.filter(coordinate=coordinate).count()
coordinate.save(update_fields=['like_count'])
```

### 3. Image Processing
- 자동 리사이징: 최대 1920px, 85% 품질
- 워터마크: Pillow로 좌상단/우하단 대각선 배치
- 저장 경로: `coordinates/%Y/%m/`, `comment_photos/%Y/%m/%d/`

### 4. HTMX Integration
```html
<div hx-get="{% url 'coordinates:list' %}"
     hx-trigger="load"
     hx-swap="innerHTML">
</div>
```

### 5. Region Auto-Detection
위도/경도로 지역 자동 감지 (Coordinate.detect_region())

---

## Deployment

```
Client → Nginx (reverse proxy) → Gunicorn (Unix socket) → Django → DB
```

### Commands
```bash
# 개발 서버
python manage.py runserver

# 마이그레이션
python manage.py makemigrations && python manage.py migrate

# 정적 파일
python manage.py collectstatic

# 프로덕션 재시작
sudo systemctl restart gunicorn
```

### Environment Variables (.env)
```
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=pikmindiary.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
ADMIN_URL=<hidden>
```

---

## Recent Features (2026)

| Date | Feature |
|------|---------|
| 01-16 | 랭킹 이모지 뱃지 시스템 (1~3등 금/은/동 테두리) |
| 01-17 | 사진 댓글 시스템 (엽서 자랑 기능) |
| 01-19 | 대댓글 알림, 마이페이지 내 댓글, 댓글 랭커 뱃지 |
| 02-03 | 댓글 좋아요 및 정렬, 아코디언 공지 UI, 워터마크 기능 |
| 02-11 | 복사 응원 메시지, N+1 쿼리 최적화, 차단 미들웨어, 접근성 개선, GitHub 연동 |

---

## Important Files

| File | Purpose |
|------|---------|
| `config/settings.py` | Django 설정 |
| `config/urls.py` | URL 라우팅 |
| `templates/base.html` | 베이스 템플릿 |
| `static/css/main.css` | 메인 스타일 |
| `apps/core/models.py` | SiteNotice, SiteSettings |

---

## Coding Conventions

### Naming
- Models: PascalCase (`CoordinateImage`)
- Views: snake_case (`coordinate_list`)
- URLs: snake_case (`coordinates:detail`)
- Templates: snake_case (`coordinate_list.html`)
- CSS: kebab-case (`comment-with-photo`)

### Model Pattern
```python
class Example(models.Model):
    """모델 설명"""
    field = models.CharField(_('필드명'), max_length=100)

    class Meta:
        verbose_name = _('예시')
        ordering = ['-created_at']
```

---

*이 문서는 새 세션에서 프로젝트를 빠르게 파악하기 위한 컨텍스트 문서입니다.*
