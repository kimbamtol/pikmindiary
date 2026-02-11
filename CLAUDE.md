# Claude 작업 지침 - Pikmin Diary

> 이 문서는 Claude가 Pikmin Diary 프로젝트 작업 시 따라야 할 지침입니다.

---

## 필독

작업 시작 전 **PROJECT_CONTEXT.md**를 읽어 프로젝트 구조를 파악하세요.

---

## 기능 변경/추가 시 필수 작업

### 1. 사이트 공지 > 업데이트 내역 추가

사용자가 체감하는 기능 변경이 있으면 **반드시** 업데이트 내역을 추가합니다.

```bash
cd /home/tori/pikmin-diary
source venv/bin/activate
python manage.py shell
```

```python
from apps.core.models import SiteNotice

notice = SiteNotice.objects.get(location='coordinates_list')
notice.update_log += "\n*기능 설명 (YY.MM.DD)"
notice.save()
```

**형식**: `*기능 설명 (YY.MM.DD)`

**예시**:
```
*댓글 좋아요 및 정렬 기능 추가 (26.02.03)
*워터마크 기능 추가 (26.02.03)
```

**업데이트 해야 하는 경우**:
- 사용자가 체감하는 새 기능 추가
- UI/UX 개선
- 중요한 버그 수정

**업데이트 불필요**:
- 내부 리팩토링
- 관리자 전용 기능

### 2. PROJECT_CONTEXT.md 업데이트

기능 변경 시 PROJECT_CONTEXT.md의 관련 섹션을 업데이트합니다:
- 새 모델 추가 → Data Models 섹션
- 새 URL 추가 → URL Structure 섹션
- 최근 기능 → Recent Features 테이블

---

## 코드 컨벤션

### 네이밍
| Type | Convention | Example |
|------|------------|---------|
| Model | PascalCase | `CoordinateImage` |
| View | snake_case | `coordinate_list` |
| URL | snake_case | `coordinates:detail` |
| Template | snake_case | `coordinate_list.html` |
| CSS | kebab-case | `comment-with-photo` |

### Django 앱 구조
```
apps/<app_name>/
├── models.py
├── views.py
├── urls.py
├── forms.py
├── admin.py
└── migrations/
```

---

## 배포 체크리스트

1. 코드 변경 완료
2. 마이그레이션 (모델 변경 시)
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
3. 정적 파일 (CSS/JS 변경 시)
   ```bash
   python manage.py collectstatic
   ```
4. Gunicorn 재시작
   ```bash
   sudo systemctl restart gunicorn
   ```
5. **사이트 공지 업데이트 내역 추가**
6. **PROJECT_CONTEXT.md 업데이트**

---

## 주의사항

- 환경 변수는 `.env`에서 관리 (하드코딩 금지)
- CSS 버전 파라미터 업데이트 필요 시: `?v=YYYYMMDD`
- 관리자 URL은 `.env`의 `ADMIN_URL` 사용

---

## 자주 사용하는 import

```python
from apps.accounts.models import CustomUser
from apps.coordinates.models import Coordinate, CoordinateImage
from apps.comments.models import Comment
from apps.interactions.models import Like, Bookmark, ValidityFeedback, Notification, CommentLike
from apps.farming.models import FarmingJournal, FarmingRequest
from apps.rankings.models import Ranking
from apps.core.models import SiteNotice, Suggestion, SiteSettings
```

---

*기능 추가/변경 후 이 지침의 필수 작업을 반드시 수행하세요.*
