# TravelMaker 기능 명세서

전체 API 엔드포인트 **29개** 기준으로 구현된 기능을 정리합니다.

---

## 목차

1. [인증 (Auth)](#1-인증-auth)
2. [사용자 프로필 (User)](#2-사용자-프로필-user)
3. [장소 (Place)](#3-장소-place)
4. [태그 (Tag)](#4-태그-tag)
5. [장소 추천 (Recommend)](#5-장소-추천-recommend)
6. [지도 / 경로 (Map)](#6-지도--경로-map)
7. [리뷰 (Review)](#7-리뷰-review)
8. [북마크 (Bookmark)](#8-북마크-bookmark)
9. [여행 퀴즈 (Travel Quiz)](#9-여행-퀴즈-travel-quiz)
10. [어드민 (Admin)](#10-어드민-admin)

---

## 1. 인증 (Auth)

카카오 OAuth2 소셜 로그인만 지원합니다. JWT 기반 인증이며 토큰은 두 가지 방식으로 저장됩니다.

- **Access Token** — 응답 body (`{"access_token": "..."}`)
- **Refresh Token** — HttpOnly 쿠키 (`refresh_token`, 7일 TTL)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| POST | `/api/v1/auth/kakao/login` | ✗ | 프론트 주도 카카오 로그인 |
| GET  | `/api/v1/auth/kakao/callback` | ✗ | 백엔드 주도 카카오 콜백 (서버→서버) |
| POST | `/api/v1/auth/token/refresh` | ✗ | Access Token 재발급 |
| POST | `/api/v1/auth/logout` | ✓ | 로그아웃 |
| DELETE | `/api/v1/auth/withdraw` | ✓ | 회원 탈퇴 (soft delete) |
| POST | `/api/v1/auth/recovery` | ✗ | 탈퇴 계정 복구 |

### 상세

#### 카카오 로그인 `POST /api/v1/auth/kakao/login`
- **요청:** `{"code": "카카오_인가_코드"}`
- **응답:** `{"access_token": "...", "is_new_user": true/false}` + Refresh Token 쿠키 세팅
- 신규 회원이면 `traveler_{랜덤5자리}` 형식의 닉네임 자동 생성
- 이미 탈퇴한 계정(14일 이내)이면 409 Conflict

#### 토큰 재발급 `POST /api/v1/auth/token/refresh`
- 쿠키의 Refresh Token을 읽어 검증
- Redis 블랙리스트에 등록된 JTI이면 403
- **fail-open 정책:** Redis 장애 시 블랙리스트 미검증(False 반환)

#### 로그아웃 `POST /api/v1/auth/logout`
- Access Token의 JTI를 Redis에 등록 (남은 TTL 만큼 유지)
- Refresh Token 쿠키 삭제

#### 회원 탈퇴 `DELETE /api/v1/auth/withdraw`
- **요청:** `{"reason": "서비스 불만족" | "개인정보" | "기타"}`
- soft delete: `is_active=False`, `deleted_at=now()`
- DB 행은 보존, 14일 이내 복구 가능

#### 계정 복구 `POST /api/v1/auth/recovery`
- **요청:** `{"code": "카카오_인가_코드"}`
- 탈퇴 후 14일이 지났으면 복구 불가 (400)
- 복구 성공 시 `is_active=True`, `deleted_at=null` 처리 후 토큰 발급

---

## 2. 사용자 프로필 (User)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET   | `/api/v1/users` | ✓ | 내 프로필 조회 |
| PATCH | `/api/v1/users` | ✓ | 내 프로필 수정 |
| PATCH | `/api/v1/users/avatar` | ✓ | 프로필 이미지 변경 |
| GET   | `/api/v1/users/bookmarks` | ✓ | 내 북마크 목록 |
| GET   | `/api/v1/users/reviews` | ✓ | 내 리뷰 목록 |
| GET   | `/api/v1/users/quiz/result` | ✓ | 내 여행 퀴즈 결과 조회 |

### 상세

#### 프로필 조회 `GET /api/v1/users`
- 응답 필드: `id`, `email`, `nickname`, `bio`, `profile_img_url`, `gender`, `birthday`, `tags`, `created_at`

#### 프로필 수정 `PATCH /api/v1/users`
- 수정 가능 필드: `nickname`(최대 14자), `bio`(최대 100자), `profile_img_url`, `tags`
- 닉네임 중복 시 409 Conflict

#### 아바타 변경 `PATCH /api/v1/users/avatar`
- **요청:** `{"travel_type_id": N}`
- 여행 성향 퀴즈 8종 중 하나를 아바타로 선택
- 해당 TravelType의 `image_url`을 `profile_img_url`에 저장

#### 내 북마크 / 내 리뷰
- 쿼리 파라미터: `?page=1&page_size=8`
- 최대 page_size: 20

#### 여행 퀴즈 결과 `GET /api/v1/users/quiz/result`
- 퀴즈를 응시한 적 없으면 404
- 응답: 성향 타입 정보 + `result_vector` (6차원)

---

## 3. 장소 (Place)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET | `/api/v1/places` | ✗ | 장소 전체 목록 |
| GET | `/api/v1/places/<id>` | ✗ | 장소 상세 조회 |
| GET | `/api/v1/places/search` | ✗ | 장소 검색 |
| GET | `/api/v1/places/filter` | ✗ | 태그 기반 필터 |

### 상세

#### 전체 목록 `GET /api/v1/places`
- `is_active=True` 인 장소만 반환
- 쿼리 파라미터: `?page=1&page_size=8` (최대 100)
- 기본 정렬: `ordering` 파라미터 지원 (`-rating_avg`, `-bookmark_count` 등)

#### 장소 상세 `GET /api/v1/places/<id>`
- 응답 필드: `id`, `place_name`, `description`, `latitude`, `longitude`, `address_primary`, `address_detail`, `tel`, `homepage`, `zipcode`, `rating_avg`, `review_count`, `bookmark_count`, `images`, `tags`

#### 장소 검색 `GET /api/v1/places/search`
- 장소명 부분 일치 검색 (`place_name__icontains`)
- 쿼리 파라미터:
  - `keyword` — 검색어
  - `sort` — `bookmark`(기본) / `review` / `rating`
  - `order` — `desc`(기본) / `asc`
  - `page`, `page_size`

#### 태그 필터 `GET /api/v1/places/filter`
- 쿼리 파라미터:
  - `tags` — 태그 ID (복수 지원: `?tags=32&tags=8` 또는 `?tags=32,8`)
  - `keyword`, `sort`, `order`, `page`, `page_size`
- 복수 태그는 **AND 조건** (모든 태그를 가진 장소만 반환)
- 지역 필터: 지역 태그 ID 사용 (서울=32, 부산=37, 제주=48 등)

**지역 태그 ID 목록**

| 지역 | ID | 지역 | ID | 지역 | ID |
|------|-----|------|-----|------|-----|
| 서울 | 32 | 경기 | 40 | 전북 | 44 |
| 인천 | 33 | 강원 | 41 | 전남 | 45 |
| 대전 | 34 | 충북 | 42 | 경북 | 46 |
| 대구 | 35 | 충남 | 43 | 경남 | 47 |
| 광주 | 36 | 세종 | 39 | 제주 | 48 |
| 부산 | 37 | 울산 | 38 | | |

---

## 4. 태그 (Tag)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET | `/api/v1/tags/` | ✗ | 전체 태그 목록 |

- 쿼리 파라미터: `?tag_type=지역` (선택, 태그 유형별 필터)
- 태그 유형 5종:

| tag_type | 내용 | 태그 수 |
|----------|------|:-------:|
| 지역 | 시·도 단위 지역 (서울~제주) | 17 |
| 세부 테마 | 해수욕·해안, 캠핑, 랜드마크 등 | 20 |
| 편의성 | 주차, 반려동물, 무료 입장 등 | 5 |
| 동행 | 혼자, 커플, 가족, 친구 | 4 |
| 여행 스타일 | 해변, 산악, 도시, 문화, 미식 등 | 7 |

---

## 5. 장소 추천 (Recommend)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET | `/api/v1/places/recommend` | ✗ | 장소 추천 (벡터 or 인기순) |

### 추천 파이프라인

```
로그인 상태?
├── Yes → 퀴즈 결과(UserTestResult) 존재?
│         ├── Yes → 벡터 기반 추천 (CosineDistance, HNSW)
│         └── No  → 인기순 폴백
└── No  → 인기순 폴백
```

#### 벡터 기반 추천
- 사용자의 `result_vector`(6차원)와 각 장소의 `style_vector`(6차원) 간 코사인 유사도 계산
- pgvector HNSW 인덱스 (m=16, ef_construction=64, cosine_ops) 활용
- `place_feature`가 없는 장소는 제외 (현재 9,545개 중 509개 태깅 완료)

#### 인기순 폴백
- `bookmark_count DESC`, `rating_avg DESC` 정렬
- 필터 없을 때 Redis 캐시 적용 (300초)

#### 쿼리 파라미터
- `region_tag_id` — 지역 태그 ID (예: `32` = 서울)
- `tags` — 추가 태그 ID 필터 (복수 지원)
- `limit` — 반환 개수 (기본 10)

---

## 6. 지도 / 경로 (Map)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET | `/api/v1/places/map` | ✗ | 전체 장소 좌표 목록 |
| GET | `/api/v1/places/map/route` | ✗ | 자동차 경로 조회 |
| GET | `/api/v1/places/config/kakao` | ✗ | 카카오맵 JS 키 발급 |

### 상세

#### 지도 좌표 목록 `GET /api/v1/places/map`
- 전체 장소의 `id`, `place_name`, `latitude`, `longitude`, `rating_avg` 반환
- 필터 파라미터 없음 (지도에 모든 핀을 표시하는 용도)

#### 경로 조회 `GET /api/v1/places/map/route`
- 카카오 모빌리티 API를 통한 자동차 경로 탐색
- 쿼리 파라미터: `origin_lat`, `origin_lng`, `place_id`
- 출발지와 도착지가 5m 이내면 오류 (`result_code: 104`)
- KAKAO_REST_API_KEY 환경변수 필요

#### 카카오맵 JS 키 `GET /api/v1/places/config/kakao`
- 응답: `{"js_key": "..."}`
- 프론트엔드에서 카카오맵 SDK 초기화에 사용

---

## 7. 리뷰 (Review)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET    | `/api/v1/places/<id>/reviews` | ✗ | 장소별 리뷰 목록 |
| POST   | `/api/v1/places/<id>/reviews` | ✓ | 리뷰 작성 |
| PATCH  | `/api/v1/reviews/<id>` | ✓ | 리뷰 수정 |
| DELETE | `/api/v1/reviews/<id>` | ✓ | 리뷰 삭제 |

### 상세

#### 리뷰 목록 `GET /api/v1/places/<id>/reviews`
- 쿼리 파라미터: `?page=1&page_size=4`
- 응답: `{"count": N, "avg_rating": 4.2, "results": [...]}`

#### 리뷰 작성 `POST /api/v1/places/<id>/reviews`
- **반드시 FormData로 전송** (JSON 불가 — `MultiPartParser` 전용)
- 요청 필드: `rating`(1~5, 필수), `content`(최대 200자), `image`(파일, 선택)
- **동일 사용자는 같은 장소에 리뷰 1개만 작성 가능** (중복 시 409 Conflict)
- 이미지 첨부 시 Celery 비동기 태스크로 S3 업로드 (재시도 3회, 60초 간격)
- 리뷰 저장 후 해당 장소의 `rating_avg`, `rating_count` 자동 갱신 (select_for_update 락)

#### 리뷰 수정 `PATCH /api/v1/reviews/<id>`
- **FormData로 전송**
- 수정 가능 필드: `rating`, `content`, `image_url` (부분 수정 가능)
- 작성자 본인만 수정 가능 (403)

#### 리뷰 삭제 `DELETE /api/v1/reviews/<id>`
- 작성자 본인만 삭제 가능 (403)
- 삭제 후 장소 평점 자동 재계산

---

## 8. 북마크 (Bookmark)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET    | `/api/v1/bookmarks/` | ✓ | 전체 북마크 목록 |
| POST   | `/api/v1/places/<id>/bookmarks/` | ✓ | 북마크 추가 |
| DELETE | `/api/v1/places/<id>/bookmarks/` | ✓ | 북마크 삭제 |

### 상세

#### 북마크 목록 `GET /api/v1/bookmarks/`
- 쿼리 파라미터: `?page=1&page_size=8` (최대 20)
- 장소 이미지 포함하여 반환

#### 북마크 추가 `POST /api/v1/places/<id>/bookmarks/`
- 응답: `{"message": "북마크가 추가되었습니다.", "bookmark_id": N}`
- 이미 북마크한 장소이면 409 Conflict

#### 북마크 삭제 `DELETE /api/v1/places/<id>/bookmarks/`
- 본인의 북마크만 삭제 가능

---

## 9. 여행 퀴즈 (Travel Quiz)

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| POST | `/api/v1/quiz/submit` | ✗ | 퀴즈 제출 및 결과 조회 |
| GET  | `/api/v1/users/quiz/result` | ✓ | 저장된 퀴즈 결과 조회 |
| PATCH | `/api/v1/users/avatar` | ✓ | 성향 타입 아바타 적용 |

### 퀴즈 채점 로직

#### 1단계 — 6축 벡터 계산

12문항 각각 A/B 선택 → 6개 축에 가중치 합산 → 정규화 (0~1)

| 축 번호 | 의미 |
|:---:|------|
| 0 | 액티비티 (활동형 ↔ 힐링형) |
| 1 | 계획성 (계획형 ↔ 즉흥형) |
| 2 | 사교성 (혼자 ↔ 단체) |
| 3 | 자연/공간 (자연형 ↔ 도시형) |
| 4 | 문화 (문화탐방형 ↔ 체험형) |
| 5 | 가성비 (가성비형 ↔ 프리미엄형) |

#### 2단계 — 성향 타입 결정 (8종)

축 0(액티비티), 2(사교성), 3(자연) 값이 0.5 이상이면 `t`, 미만이면 `f`

| type_key | 이름 예시 |
|----------|----------|
| ttt | 새벽을 달리는 늑대 |
| ttf | (도시 액티비티 혼자형) |
| tft | (자연 액티비티 단체형) |
| tff | (도시 액티비티 단체형) |
| ftt | (자연 힐링 혼자형) |
| ftf | (도시 힐링 혼자형) |
| fft | (자연 힐링 단체형) |
| fff | (도시 힐링 단체형) |

#### 3단계 — 장소 즉시 추천

결과 벡터와 장소 `style_vector` 간 코사인 유사도로 **상위 3개** 장소 즉시 반환

#### 퀴즈 응답 형식

```json
{
  "saved": true,
  "travel_type": { "type_key": "ttt", "name": "새벽을 달리는 늑대" },
  "type_tags": ["액티비티형", "혼자형", "자연형"],
  "description": "체력을 아낌없이 쓰는 활동형 여행자예요...",
  "detail_cards": [
    { "title": "몸으로 떠나는 여행", "description": "..." },
    ...
  ],
  "result_vector": [0.7, 0.6, 0.8, 0.6, 0.4, 0.3],
  "recommended_places": [...]
}
```

- 비로그인 상태로 제출하면 `saved: false` (결과는 반환되나 저장 안 됨)
- 재응시 가능: `update_or_create`로 기존 결과 덮어쓰기

---

## 10. 어드민 (Admin)

`role=ADMIN` 권한 필요. 일반 유저 접근 불가 (403).

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| GET    | `/api/v1/admin/users` | 전체 유저 목록 조회 (페이징) |
| POST   | `/api/v1/admin/places` | 장소 직접 등록 |
| PUT    | `/api/v1/admin/places/<id>` | 장소 전체 수정 |
| DELETE | `/api/v1/admin/places/<id>` | 장소 삭제 |
| GET    | `/api/v1/admin/reviews` | 전체 리뷰 목록 조회 (페이징) |
| DELETE | `/api/v1/admin/reviews/<id>` | 리뷰 강제 삭제 |

---

## 부록 — 공통 규격

### 에러 응답 형식

모든 API 에러는 아래 형식으로 반환됩니다.

```json
{ "error_detail": "설명 메시지" }
```

### 페이지네이션 응답 형식

```json
{
  "count": 42,
  "next": "http://.../api/v1/places?page=2",
  "previous": null,
  "results": [...]
}
```

### 주요 제약 조건

| 항목 | 제약 |
|------|------|
| 닉네임 | 최대 14자, 중복 불가 |
| 자기소개 | 최대 100자 |
| 리뷰 별점 | 1~5 정수 |
| 리뷰 내용 | 최대 200자 |
| 리뷰 중복 | 사용자당 장소별 1개만 허용 |
| 북마크 중복 | 사용자당 장소별 1개만 허용 |
| 팔로우 중복 | follower + following 쌍 unique |
| 탈퇴 복구 기간 | 탈퇴 후 14일 이내 |
| 퀴즈 저장 | 로그인 시에만 저장 (재응시 시 덮어쓰기) |

### 인프라 의존성

| 서비스 | 용도 |
|--------|------|
| PostgreSQL + pgvector | 주 데이터베이스, 벡터 유사도 검색 |
| Redis | JWT 블랙리스트, Celery 브로커/결과, 인기 장소 캐시 |
| AWS S3 | 리뷰 이미지 저장 |
| Celery Worker | S3 이미지 업로드 비동기 처리 (재시도 3회) |
| 카카오 OAuth2 | 소셜 로그인 |
| 카카오 모빌리티 API | 자동차 경로 탐색 |
