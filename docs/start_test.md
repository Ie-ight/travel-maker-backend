# 로컬 테스트 실행 가이드

## 목차
1. [사전 요구사항](#1-사전-요구사항)
2. [초기 설정 (최초 1회)](#2-초기-설정-최초-1회)
3. [서버 실행](#3-서버-실행)
4. [테스트 콘솔 사용법](#4-테스트-콘솔-사용법)
5. [플로우차트 보기](#5-플로우차트-보기)

---

## 1. 사전 요구사항

| 항목 | 확인 방법 |
|---|---|
| PostgreSQL 실행 중 | `psql -U postgres -c "\l"` |
| Redis 실행 중 | `redis-cli ping` → `PONG` |
| uv 설치 | `uv --version` |

> Docker를 사용하는 경우:
> ```bash
> docker compose -f infrastructure/docker/docker-compose.yml up -d db redis
> ```

---

## 2. 초기 설정 (최초 1회)

### 의존성 설치
```bash
uv sync --all-extras
```

### 마이그레이션
```bash
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py migrate
```

### 시드 데이터 적재

**여행 성향 타입 8종 (퀴즈 기능 필수)**
```bash
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py seed_travel_types
```

**태그 데이터 (지역·테마·편의성·동행·여행스타일)**
```bash
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py seed_tags
```

**장소 데이터 복원 (dumps/ 폴더)**

> 자세한 내용은 `dumps/RESTORE.md` 참고

```bash
# Docker db 컨테이너로 덤프 파일 복사
docker compose -f infrastructure/docker/docker-compose.yml cp dumps/place_dump_*.dump db:/tmp/

# 컨테이너 안에서 복원
docker compose -f infrastructure/docker/docker-compose.yml exec db \
  pg_restore --data-only --no-owner --disable-triggers \
  -U travel_maker_user -d travel_maker_db /tmp/place_dump_*.dump
```

복원 확인:
```bash
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py shell -c \
  "from apps.place.models import Place, PlaceFeature; print('장소', Place.objects.count(), '/ 태깅', PlaceFeature.objects.count())"
# 장소 9545 / 태깅 509
```

---

## 3. 서버 실행

**두 터미널을 각각 열어서 실행합니다.**

### 터미널 1 — Django 서버 (포트 8000)
```bash
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py runserver
```

### 터미널 2 — 프론트 HTTP 서버 (포트 3000)
```bash
python -m http.server 3000 --directory test_frontend
```

> 두 서버 모두 실행 중이어야 테스트 콘솔이 정상 작동합니다.

---

## 4. 테스트 콘솔 사용법

브라우저에서 접속:
```
http://localhost:3000/console.html
```

### 사이드바 메뉴 구성

| 메뉴 | 테스트 가능 기능 |
|---|---|
| 🔐 인증 | 카카오 로그인 · 로그아웃 · 토큰 갱신 · 탈퇴 · 계정 복구 |
| 👤 프로필 | 프로필 조회/수정 · 내 북마크 · 내 리뷰 · 퀴즈 결과 · 아바타 변경 |
| 📍 장소 | 목록 · 검색 · 필터 · 상세 조회 |
| 🏷 태그 | 전체 태그 목록 조회 |
| 🗺 지도/추천 | 카카오맵 키 · 장소 추천 · 지도 좌표 · 경로 조회 |
| 🔖 북마크 | 북마크 추가/삭제 · 목록 조회 |
| ⭐ 리뷰 | 리뷰 목록/작성/수정/삭제 |
| 🧩 여행 퀴즈 | 12문항 응시 → 성향 타입 결정 → 장소 추천 |

### 주의사항

**카카오 로그인**
- Kakao Developers 콘솔에 `http://localhost:3000/social-callback` 이 Redirect URI로 등록되어 있어야 합니다.
- 로그인 완료 후 자동으로 콘솔로 복귀합니다.

**리뷰 작성**
- 이미지를 첨부하면 presigned URL을 발급받아 S3에 직접 업로드한 뒤, 그 URL을 `image_url`로 담아 JSON으로 전송합니다.
- 같은 장소에 리뷰는 1개만 작성 가능합니다.

**경로 조회**
- 출발지와 도착지가 5m 이내면 카카오 모빌리티 API 오류(`result_code: 104`)가 발생합니다.
- 테스트 출발 좌표 예시: 서울역 `37.5547, 126.9707` / 강남역 `37.4979, 127.0276`

**장소 필터**
- 지역은 드롭다운에서 선택합니다 (서울=32, 부산=37, 제주=48 등 태그 ID).
- 텍스트 입력 불가 — 태그 ID 기반 AND 필터입니다.

---

## 5. 플로우차트 보기

`docs/flowchart.html` 파일을 더블클릭하거나 아래 명령으로 열 수 있습니다.

```powershell
# Windows
Start-Process docs\flowchart.html
```

### 탭 구성

| 탭 | 내용 |
|---|---|
| 🗺 전체 개요 | 서비스 전체 흐름 한눈에 보기 |
| 🔐 인증 | 카카오 OAuth2 · JWT 발급/갱신/블랙리스트 |
| 📍 장소 | 목록·검색·필터·상세·지도·경로 흐름 |
| 🧭 추천 | 벡터 기반 추천 vs 인기순 폴백 파이프라인 |
| 🧩 여행 퀴즈 | 벡터 계산 → 성향 타입 결정 전체 흐름 |
| ⭐ 리뷰 | 작성·수정·삭제·S3 비동기 업로드 |
| 🔖 북마크 | 추가·삭제·목록 조회 |
| 👤 프로필 | 조회·수정·아바타 변경 |

> 인터넷 연결이 필요합니다 (Mermaid.js CDN 로드).
