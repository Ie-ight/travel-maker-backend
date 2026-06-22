# Travel Maker Backend

AI 기반 여행지 추천 플랫폼의 백엔드 서버입니다. 사용자의 여행 성향 퀴즈 결과와 행동 데이터를 바탕으로 개인화된 장소를 추천하고, 여행 경로 계획부터 공유까지 지원합니다.

- **서비스**: https://www.travel-maker.site/
- **API 문서 (Swagger)**: https://api.travel-maker.site/api/docs/
- **관리자**: https://api.travel-maker.site/admin/

---

## 프로젝트 소개

사용자가 여행 성향 퀴즈를 풀면 6차원 성향 벡터가 생성되고, 이 벡터와 장소별 AI 분석 벡터 간의 코사인 유사도를 기반으로 장소를 추천합니다. 사용자의 북마크·리뷰·경로 추가 등 행동이 누적되면 1024차원 임베딩 벡터로 전환되어 더 정밀한 개인화 추천이 제공됩니다.

---

## 핵심 기능

### 3단계 개인화 추천 (S1 → S2 → S3)

장소 추천은 사용자 상태에 따라 단계적으로 고도화됩니다.

```
S1 (비로그인 / 퀴즈 미완료)
  → 인기순 정렬 (rating_avg, bookmark_count)

S2 (여행 성향 퀴즈 완료)
  → 퀴즈 결과 6차원 벡터 ↔ 장소 style_vector 코사인 유사도
  → HNSW 인덱스 ANN 쿼리 (pgvector)

S3 (행동 데이터 임계값 도달)
  → 북마크·리뷰·경로 추가 행동을 가중합산한 1024차원 임베딩 벡터
  → content_vector HNSW ANN 쿼리
```

### 하이브리드 검색

키워드 + 벡터를 결합한 3단계 폴백 검색 구조입니다.

```
1단계: 장소명 / 태그 정확 매칭 (place_name, tags)
2단계: 주소 매칭 (address_primary)
3단계: pg_trgm trigram 유사도 (오타 허용)
```

키워드 매칭이 있으면 `combined score = 0.7 × 벡터 유사도 + 0.3 × 키워드 연관도`로 정렬합니다.

### AI 태깅 & 벡터 생성

장소 설명(overview)을 LLM에 전달해 스타일 태그와 6차원 성향 벡터를 자동 생성합니다.

- **태그 유형**: 여행 스타일, 세부 테마, 동행
- **6차원 성향 축**: 활동성, 계획성, 사교성, 공간지향, 경험지향, 소비스타일
- **Provider 토글**: Gemini (`gemini-2.0-flash` 등) / Ollama (로컬 모델)

텍스트 임베딩(content_vector, 1024D)도 동일한 토글 구조로 지원합니다.

- Ollama: `bge-m3` (로컬, 1024D)
- Gemini: `gemini-embedding-001` (`output_dimensionality=1024`)

### 여행 성향 퀴즈

퀴즈 응답을 집계해 6차원 `result_vector`와 여행 유형(TravelType)을 산출합니다. 결과는 S2 추천의 입력 벡터로 사용되며, 비로그인 유저도 공유 URL로 결과를 전달할 수 있습니다.

### 경로(Route) 계획

- 최대 5일 일정, 일차당 최대 5곳 장소 구성
- 지역 태그 및 테마 태그로 경로 분류
- 경로 좋아요 기능

### 소셜 & 커뮤니티

- **팔로우**: 유저 간 팔로우/팔로잉 그래프
- **북마크**: 장소 저장 (bookmark_count 비정규화 컬럼으로 정렬 가속)
- **리뷰**: 장소당 1인 1리뷰, 별점(1–5) + 내용 + 이미지, Celery 비동기 이미지 처리

### 공유

장소, 경로, 퀴즈 결과를 프론트엔드 딥링크 URL로 변환해 공유합니다.

### 인증 (Kakao OAuth2)

- **프론트엔드 주도**: `POST /api/v1/auth/kakao/login` — 프론트가 auth code를 백엔드에 전달
- **백엔드 콜백**: `GET /api/v1/auth/kakao/callback` — Kakao 리디렉션 처리 후 프론트로 302
- **Access token**: 응답 body
- **Refresh token**: HttpOnly 쿠키 (7일 TTL)
- **블랙리스트**: Redis (JTI 기반, DB 블랙리스트 미사용)
- **소프트 삭제**: 탈퇴 시 `is_active=False` + `deleted_at`, 14일 이내 `POST /api/v1/auth/recovery`로 복구 가능

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| Framework | Django 5.1, Django REST Framework |
| 데이터베이스 | PostgreSQL + pgvector (HNSW 인덱스, pg_trgm) |
| 캐시 / 메시지 브로커 | Redis |
| 비동기 태스크 | Celery + django-celery-beat + Flower |
| AI / LLM | Google Gemini, Ollama (bge-m3) |
| 인증 | SimpleJWT + Kakao OAuth2 |
| 스토리지 | AWS S3 (boto3) |
| 모니터링 | Sentry |
| API 문서 | drf-spectacular (Swagger / ReDoc) |
| 테스트 | pytest, factory-boy, pytest-cov |
| Lint / Format | Ruff |
| 타입 검사 | mypy (strict) |
| 패키지 관리 | uv |

---

## 아키텍처

### 레이어 구조

각 앱은 다음 4계층을 엄격히 분리합니다.

```
views/        HTTP 파싱 및 응답만 담당. 비즈니스 로직 없음.
services/     모든 비즈니스 로직. 모델 조합 및 외부 API 호출.
serializers/  요청 유효성 검사 및 응답 직렬화.
schemas/      drf-spectacular @extend_schema 데코레이터 (OpenAPI 전용).
```

### 앱 구성

```
apps/
├── core/          TimeStampModel, 공통 예외, S3 Presigned URL
├── user/          User, SocialUser, Follow, UserPreference, UserActionLog
├── place/         Place, PlaceFeature (벡터), Tag, PlaceInfo
├── review/        Review (유저×장소 1건)
├── bookmark/      Bookmark
├── route/         Route, RouteDay, RouteDayPlace, RouteLike
├── travel_quiz/   TravelType, UserTestResult
└── share/         공유 URL 생성
```

### 추천 파이프라인

```
요청 → determine_stage(user_id)
         │
         ├─ S1 → 인기순 (rating_avg DESC, bookmark_count DESC)
         │
         ├─ S2 → UserTestResult.result_vector (6D)
         │         └─ PlaceFeature.style_vector HNSW ANN
         │
         └─ S3 → UserPreference.content_vector (1024D)
                   └─ PlaceFeature.content_vector HNSW ANN

키워드 있는 경우 → 하이브리드 검색 (DB 필터 + 코사인 유사도 + trgm combined score)
```

### 데이터 수집 파이프라인

```
한국관광공사 Tour API
  → Place / PlaceImage / PlaceInfo 저장
  → AI 분석 (Gemini / Ollama)
      → Tag (여행 스타일, 세부 테마, 동행) 부여
      → PlaceFeature.style_vector (6D) 저장
  → 텍스트 임베딩 (bge-m3 / Gemini Embedding)
      → PlaceFeature.content_vector (1024D) 저장
```

---

## 에러 응답 형식

모든 API 오류는 아래 단일 형태로 반환됩니다.

```json
{
  "error_detail": "오류 메시지"
}
```

HTTP 상태 코드는 표준 코드를 따릅니다 (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict 등).

---

## API 문서

- **Swagger UI**: https://api.travel-maker.site/api/docs/
- **ReDoc**: https://api.travel-maker.site/api/redoc/

로컬 개발 환경에서는 `/api/docs/`, `/api/redoc/`에서 확인할 수 있습니다.

### 주요 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/v1/auth/kakao/login` | 카카오 로그인 |
| GET | `/api/v1/auth/kakao/callback` | 카카오 OAuth 콜백 |
| POST | `/api/v1/auth/logout` | 로그아웃 (토큰 블랙리스트) |
| POST | `/api/v1/auth/withdrawal` | 회원 탈퇴 (소프트 삭제) |
| POST | `/api/v1/auth/recovery` | 탈퇴 계정 복구 |
| GET | `/api/v1/places` | 장소 목록 (정렬·태그 필터) |
| GET | `/api/v1/places/search` | 키워드 검색 |
| GET | `/api/v1/places/recommend` | 개인화 추천 (S1/S2/S3) |
| GET | `/api/v1/places/<id>` | 장소 상세 |
| POST | `/api/v1/places/<id>/bookmarks/` | 북마크 토글 |
| GET/POST | `/api/v1/reviews` | 리뷰 목록 / 작성 |
| GET/POST | `/api/v1/routes` | 경로 목록 / 생성 |
| POST | `/api/v1/quiz/submit` | 여행 성향 퀴즈 제출 |
| POST | `/api/v1/share` | 공유 URL 생성 |
| GET | `/api/v1/tags/` | 태그 목록 |

---

## 배포 구조

`main` 브랜치에 push되면 GitHub Actions가 자동으로 빌드·배포합니다.

```
GitHub Actions
  ├─ Docker Hub에 이미지 빌드 & 푸시
  │    ├─ travel-maker-web        (gunicorn)
  │    ├─ travel-maker-celery-worker
  │    ├─ travel-maker-celery-beat
  │    └─ travel-maker-flower
  └─ EC2 SSH 접속 → docker compose pull → up -d → migrate → healthcheck
```

프로덕션 컨테이너 구성 (`infrastructure/docker/docker-compose.prod.yml`):

| 컨테이너 | 역할 |
|---|---|
| `web` | gunicorn (workers=2, port 8000) |
| `celery_worker` | 비동기 태스크 처리 (이미지 업로드, 행동 벡터 갱신 등) |
| `celery_beat` | 주기적 예약 태스크 실행 |
| `flower` | Celery 태스크 모니터링 (port 5555, Basic Auth) |
| `db` | pgvector/pgvector:pg16 |
| `redis` | 캐시 & 메시지 브로커 |

정적 파일은 Nginx가 서빙하며, 배포 시 컨테이너에서 호스트 `/var/www/`로 복사됩니다.

---

## CI/CD

| 워크플로 | 트리거 | 내용 |
|---|---|---|
| `ci-lint.yml` | PR, `main`/`dev` push | Ruff 린트 + mypy 타입 검사 |
| `ci-test.yml` | PR, `main`/`dev` push | pytest (PostgreSQL + Redis 서비스 컨테이너) |
| `deploy.yml` | `main` push | Docker Hub 빌드 → EC2 배포 |

---

## 브랜치 전략 & 커밋 컨벤션

### 브랜치

```
main   배포 브랜치. push 시 자동 배포.
dev    개발 통합 브랜치.
feat/  기능 브랜치. dev에서 분기 후 PR로 병합.
fix/   버그 수정 브랜치.
```

### 커밋 타입

| 타입 | 설명 |
|---|---|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 수정 |
| `style` | 코드 포맷팅 (기능 변경 없음) |
| `refactor` | 리팩토링 (기능 변경 없음) |
| `test` | 테스트 코드 추가/수정 |
| `chore` | 빌드, 패키지 설정 등 |

---

## 개발 환경 설정

### 사전 요구사항

- Python 3.12+
- PostgreSQL (pgvector 확장 포함)
- Redis

### 설치 및 실행

```bash
# 의존성 설치
uv sync --all-extras

# 마이그레이션
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py migrate

# 개발 서버 실행
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py runserver
```

### 테스트

```bash
# 전체 테스트
uv run pytest

# 특정 파일
uv run pytest apps/user/tests/test_auth.py

# 커버리지 포함
uv run pytest --cov --cov-report=term-missing

# 병렬 실행
uv run pytest -n auto
```

### 코드 품질

```bash
uv run ruff check .    # 린트
uv run ruff format .   # 포맷
uv run mypy .          # 타입 검사
```

### 관리 명령어

초기 데이터 구성이나 AI 파이프라인 실행 시 사용하는 management commands입니다.

```bash
# 태그 시드 데이터 삽입 (여행 스타일, 세부 테마, 동행, 지역, 편의성)
uv run python manage.py seed_tags

# 여행 유형(TravelType) 시드 데이터 삽입
uv run python manage.py seed_travel_types

# Tour API 분류 코드 동기화
uv run python manage.py sync_lcls_codes

# 장소에 AI 태그 및 style_vector 생성
uv run python manage.py ai_tag

# 장소 텍스트 임베딩(content_vector) 생성
uv run python manage.py embed_places

# 결정론적 태그 재부여 (AI 태그 외 지역·편의성 등)
uv run python manage.py assign_tags
```

### 환경 변수

```
SECRET_KEY
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
REDIS_CACHE_URL
CELERY_BROKER_URL, CELERY_RESULT_BACKEND
KAKAO_CLIENT_ID, KAKAO_JS_KEY, KAKAO_REST_API_KEY, KAKAO_REDIRECT_URI
FRONTEND_URL
GEMINI_API_KEY
OLLAMA_HOST, OLLAMA_MODEL
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME
```
