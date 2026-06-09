# plan.md

TravelMaker 백엔드 구현 현황 및 남은 작업 계획.
새 기능 작업 전 이 문서를 읽고, 완료된 항목은 `[x]`로 체크하며 업데이트한다.

---

## 내일 바로 할 일 (2026-06-06 기준)

### Step 1 — PR/브랜치 마무리 (우선)

PR #76 (`feat/sort` → `dev`) CI ✅ 통과, 리뷰 후 머지 대기 중.
**머지 완료 후 순서대로:**

1. **`feat/quiz-result` push + PR 생성**
   - 로컬 브랜치에 커밋(`e0d64eb`)은 있으나 push 안 됨
   - stash도 있음 → `git stash list` 확인 후 필요시 적용
   - PR base: `dev`
   - `git push origin feat/quiz-result` → `gh pr create`

2. **`feat/kakao-callback` rebase + PR 업데이트**
   - 현재 PR base: `feat/sort` (올바름)
   - feat/sort가 dev에 머지되면 → `git rebase origin/dev` → `git push --force-with-lease`
   - PR base를 `dev`로 변경: `gh pr edit <번호> --base dev`

### Step 2 — 기능 구현 우선순위

| 순서 | Phase | 내용 | 예상 소요 |
|---|---|---|---|
| 1 | Phase 1 | 유저 관심 태그 API | 소 |
| 2 | Phase 4 | 팔로우 API | 중 |
| 3 | Phase 5 | 팔로우 피드 API | 중 |
| 4 | Phase 6 | S3 이미지 업로드 | 중 |
| 5 | Phase 7 | Celery Beat 증분 동기화 | 소 |

---

## 현황 요약

| 앱 | 상태 | 비고 |
|---|---|---|
| `apps/core` | ✅ 완료 | 공통 모델, 예외 핸들러, 페이지네이션, Redis 키 관리 |
| `apps/user` — 인증 | ✅ 완료 | 카카오 OAuth2 백엔드 콜백 방식, JWT, refresh, logout, withdrawal, recovery |
| `apps/user` — 프로필 | ✅ 완료 | GET/PATCH, 내 북마크 목록, 내 리뷰 목록 |
| `apps/user` — 관심 태그 | 🔲 미구현 | `User.tags` M2M 모델만 존재. API 없음 |
| `apps/user` — 팔로우 | 🔲 미구현 | `Follow` 모델만 존재. API 없음 |
| `apps/place` — 장소 CRUD | ✅ 완료 | list, search, filter, detail |
| `apps/place` — 태그 | ✅ 완료 | 태그 목록 API, 관심 태그 기반 필터 |
| `apps/place` — 지도 | ✅ 완료 | 마커 목록, 경로(Kakao Mobility 프록시), JS키 |
| `apps/place` — 데이터 파이프라인 | ✅ 완료 | sync_places, ai_tag, assign_tags 등 management commands |
| `apps/place` — 추천 API | ✅ 완료 | pgvector HNSW 코사인 유사도 기반 추천 (`feat/sort` PR #76) |
| `apps/review` | ✅ 완료 | CRUD, 이미지 Celery 비동기 처리 |
| `apps/review` — S3 업로드 | 🔲 미구현 | 현재 이미지 URL 직접 저장 |
| `apps/bookmark` | ✅ 완료 | 생성/삭제 |
| `apps/travel_quiz` — 퀴즈 결과 | ✅ 완료 | POST/GET `/api/v1/quiz/result` (`feat/quiz-result` 로컬, push 필요) |
| 증분 동기화 스케줄 | 🔲 미구현 | Celery Beat + `sync_places --sync` |

---

## 구현된 API 목록

### 인증 (`/api/v1/auth/`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `kakao/callback` | 카카오 콜백 (백엔드 주도 302 리다이렉트) |
| POST | `token/refresh` | 액세스 토큰 재발급 |
| POST | `logout` | 로그아웃 (refresh 토큰 블랙리스트) |
| DELETE | `withdrawal` | 회원 탈퇴 (soft delete) |
| POST | `recovery` | 탈퇴 계정 복구 (14일 이내) |

### 유저 (`/api/v1/`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET/PATCH | `users/me` | 내 프로필 조회/수정 |
| GET | `users/me/bookmarks` | 내 북마크 목록 |
| GET | `users/me/reviews` | 내 리뷰 목록 |

### 장소 (`/api/v1/places/`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `` | 장소 목록 (페이지네이션) |
| GET | `search` | 키워드 검색 |
| GET | `filter` | 태그 필터 |
| GET | `recommend` | 유저 성향 벡터 기반 추천 (pgvector HNSW) |
| GET | `<place_id>` | 장소 상세 |
| GET | `map` | 지도 마커 좌표 목록 |
| GET | `map/route` | 경로 조회 (Kakao Mobility 프록시) |
| GET | `config/kakao` | Kakao JS 키 반환 |
| POST/DELETE | `<place_id>/bookmarks/` | 북마크 생성/삭제 |

### 태그 (`/api/v1/tags/`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `` | 전체 태그 목록 |

### 퀴즈 (`/api/v1/`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `quiz/result` | 퀴즈 결과 저장/갱신 (travel_type_key + result_vector) |
| GET | `quiz/result` | 내 퀴즈 결과 조회 |

### 리뷰 (`/api/v1/`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET/POST | `places/<place_id>/reviews/` | 리뷰 목록 / 작성 |
| PATCH/DELETE | `reviews/<review_id>/` | 리뷰 수정 / 삭제 |

---

## 남은 작업 — 우선순위 순

### Phase 1 — 유저 관심 태그 API

`User.tags` (M2M → `place.Tag`) 필드가 모델에 존재하지만 등록/조회 API가 없다.
추천 API의 선행 조건이므로 먼저 구현한다.

- [ ] `GET /api/v1/users/me/tags` — 내 관심 태그 조회
- [ ] `PUT /api/v1/users/me/tags` — 관심 태그 전체 교체
- [ ] 테스트: `apps/user/tests/test_profile.py` 확장

구현 파일:
```
apps/user/serializers/profile_serializer.py   # 태그 시리얼라이저 추가
apps/user/services/profile_service.py         # 태그 교체 로직
apps/user/views/profile_view.py               # UserTagView 추가
apps/user/urls/user_urls.py                   # URL 등록
apps/user/schemas/profile_schema.py           # @extend_schema 추가
```

---

### Phase 2 — 유저 성향 설문 + `user_features` 벡터 ✅ 완료 (travel_quiz로 대체)

`apps/travel_quiz` 앱의 `UserTestResult` 모델(travel_type + result_vector VECTOR(6))로 구현 완료.
`POST/GET /api/v1/quiz/result` (`feat/quiz-result` 브랜치 — **push/PR 필요**).

---

### Phase 3 — pgvector 기반 장소 추천 API ✅ 완료

`GET /api/v1/places/recommend` 구현 완료 (`feat/sort` PR #76 머지 대기).

- HNSW 인덱스(`vector_cosine_ops`) 활용, `SET LOCAL hnsw.iterative_scan = strict_order`
- over-fetch(×4) → Python dedup → Place 2차 쿼리 enrichment
- 비로그인/벡터 없는 경우 인기순(북마크 수) 폴백 + Redis 캐시(TTL 300s)

---

### Phase 4 — 팔로우 API

`Follow` 모델은 구현되어 있으나 API가 없다.

- [ ] `POST /api/v1/users/<user_id>/follow` — 팔로우
- [ ] `DELETE /api/v1/users/<user_id>/follow` — 언팔로우
- [ ] `GET /api/v1/users/<user_id>/followers` — 팔로워 목록
- [ ] `GET /api/v1/users/<user_id>/followings` — 팔로잉 목록
- [ ] 테스트

구현 파일:
```
apps/user/serializers/follow_serializer.py    # 새 파일
apps/user/services/follow_service.py          # 새 파일
apps/user/views/follow_view.py               # 새 파일
apps/user/urls/user_urls.py                   # URL 등록
apps/user/schemas/follow_schema.py           # 새 파일
```

---

### Phase 5 — 팔로우 피드 API

Phase 4 완료 후 진행.

- [ ] `GET /api/v1/feed` — 팔로잉한 유저의 최신 리뷰 피드
  - 정렬: `created_at DESC`
  - 페이지네이션: 기본 `page_size=8`
- [ ] 테스트

구현 파일:
```
apps/review/serializers/review_serializers.py  # 피드용 시리얼라이저 추가
apps/review/services/review_services.py        # 피드 쿼리 함수 추가
apps/review/views/review_views.py             # FeedView 추가
apps/review/urls.py                           # URL 등록
apps/review/schemas/review_schemas.py         # @extend_schema 추가
```

---

### Phase 6 — 리뷰 이미지 S3 업로드

현재 이미지 URL을 직접 저장. S3 presigned URL 방식으로 교체.

- [ ] S3 연동 설정 (`django-storages`, `boto3`)
  - 환경변수: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`
- [ ] `POST /api/v1/reviews/image-upload` — presigned URL 발급 (인증 필요)
- [ ] 리뷰 작성/수정 시 S3 URL 검증 로직
- [ ] Celery 태스크 교체 (URL 저장 → S3 URL 검증)
- [ ] 테스트

---

### Phase 7 — 증분 동기화 스케줄 (Celery Beat)

`sync_places --sync` 커맨드는 구현되어 있으므로 Beat 스케줄만 연결하면 된다.

- [ ] `celery_beat` 스케줄 설정 (`CELERY_BEAT_SCHEDULE`)
  - 주기: 월 1회 (운영 환경 기준)
  - 태스크: `sync_places --sync` → Celery 태스크로 래핑
- [ ] 태스크 완료 알림 또는 로깅 확인
- [ ] 테스트

구현 파일:
```
apps/place/tasks.py                           # sync_places 태스크 추가
config/settings/base.py                       # CELERY_BEAT_SCHEDULE 추가
```

---

### Phase 8 — Redis 키 관리 (`apps/core/cache.py`) ✅ 완료

모든 Redis cache key는 `apps/core/cache.py`에서 생성 함수로 정의한다. 서비스 코드에 문자열 하드코딩 금지.

- [x] `blacklist_key(jti)` → `blacklist:{jti}` (JWT 블랙리스트)
- [x] `popular_places_fallback_key(limit)` → `popular_places:limit:{N}` (추천 폴백 캐시)
- 향후 Redis 용도 추가 시 이 파일에 먼저 키 함수 정의

---

## 개발 규칙 요약

- **레이어 분리 필수**: views → services → serializers. 비즈니스 로직은 services에만.
- **테스트 선행**: Red → Green → Refactor.
- **에러 응답**: 항상 `{"error_detail": "..."}` 형태.
- **스키마 데코레이터**: `@extend_schema`는 앱의 `schemas/` 모듈에서 import, 뷰 인라인 금지.
- **동작 변경과 구조 변경은 별도 커밋**.

상세 규칙은 `AGENTS.md`, 설계 배경은 `SYSTEM_DESIGN.md` 참고.
