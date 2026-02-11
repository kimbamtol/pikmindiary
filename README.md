# 피크민 다이어리 (Pikmin Diary)

> 피크민 블룸 좌표 공유 커뮤니티 - [pikmindiary.com](https://pikmindiary.com)

피크민 블룸 게임의 버섯, 모종, 빅플라워 좌표를 공유하고, 파밍 활동을 기록하는 커뮤니티 플랫폼입니다.

## 주요 기능

- **좌표 공유** - 버섯, 모종, 빅플라워 위치 등록 및 검색
- **지도 탐색** - 등록된 좌표를 지도에서 한눈에 확인
- **파밍 일지** - 파밍 활동 기록 및 도움 요청
- **댓글 & 대댓글** - 사진 첨부 지원 (엽서 자랑)
- **좋아요 & 북마크** - 관심 좌표 저장
- **유효성 평가** - 커뮤니티 기반 좌표 검증
- **랭킹 시스템** - 기여도 기반 점수 및 순위
- **워터마크** - 업로드 이미지에 자동 워터마크 적용
- **지역 자동 감지** - 위도/경도로 지역 자동 분류
- **비회원 지원** - 로그인 없이도 등록, 댓글, 좋아요 가능

## 기술 스택

| 분류 | 기술 |
|------|------|
| Backend | Python 3.12, Django 6.0 |
| Frontend | HTML/CSS/JS, HTMX |
| Auth | django-allauth (Google OAuth) |
| Image | Pillow |
| Deploy | Nginx + Gunicorn + Systemd |

## 실행 방법

```bash
# 가상환경
python -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env  # 필요한 값 채우기

# DB 마이그레이션
python manage.py migrate

# 개발 서버 실행
python manage.py runserver
```

## 환경변수 (.env)

```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
ADMIN_URL=your-admin-url
```

## 라이선스

이 프로젝트는 개인 프로젝트로, 무단 복제 및 배포를 금합니다.

---

*이 사이트는 Nintendo 또는 Niantic과 관련이 없습니다.*
