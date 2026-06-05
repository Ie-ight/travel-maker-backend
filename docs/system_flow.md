# TravelMaker 전체 시스템 플로우

## 1. 전체 아키텍처

```mermaid
graph TB
    subgraph Client
        FE[프론트엔드<br/>Next.js]
    end

    subgraph Django["Django REST API (Gunicorn)"]
        U[apps/user<br/>인증·프로필·팔로우]
        P[apps/place<br/>장소·추천·태그]
        R[apps/review<br/>리뷰·이미지]
        B[apps/bookmark<br/>북마크]
    end

    subgraph Async["비동기 처리"]
        CW[Celery Worker<br/>태스크 실행]
        CB[Celery Beat<br/>스케줄 관리]
    end

    subgraph Storage["저장소"]
        Redis[(Redis 7<br/>db=0: JWT 블랙리스트<br/>db=1: Celery Broker<br/>db=2: Celery Results)]
        DB[(PostgreSQL 16<br/>+ pgvector)]
        S3[(AWS S3<br/>이미지)]
        TourAPI[한국관광공사<br/>Tour API]
        Gemini[Google Gemini API<br/>AI 태깅]
    end

    FE -->|HTTP/JWT| Django
    Django -->|읽기/쓰기| DB
    Django -->|JWT 블랙리스트| Redis
    Django -->|태스크 적재| Redis
    CW -->|태스크 수신| Redis
    CB -->|스케줄 태스크 적재| Redis
    CW -->|이미지 업로드| S3
    CW -->|장소 동기화| TourAPI
    CW -->|AI 태깅| Gemini
    CW -->|결과 저장| DB
```

---

## 2. 사용자 흐름 (End-to-End)

```mermaid
sequenceDiagram
    actor User as 사용자
    participant FE as 프론트엔드
    participant Django as Django 서버
    participant DB as PostgreSQL
    participant Redis as Redis

    User->>FE: 카카오 로그인
    FE->>Django: POST /api/v1/auth/kakao/login
    Django->>DB: User 조회 또는 생성
    Django->>Redis: (로그아웃 시) JTI 블랙리스트 저장
    Django-->>FE: Access Token + Refresh Token(Cookie)
    FE-->>User: 로그인 완료

    User->>FE: 여행지 탐색 (검색·태그 필터·정렬)
    FE->>Django: GET /api/v1/places/?keyword=&sort=bookmark&tags=1&tags=3
    Django->>DB: is_active=True 필터 + bookmark/review count annotate + 정렬
    Django-->>FE: 장소 목록 (페이지네이션)
    FE-->>User: 장소 카드 표시

    User->>FE: 장소 상세 클릭
    FE->>Django: GET /api/v1/places/{id}/
    Django->>DB: 장소 상세 + 이미지·태그 prefetch
    Django-->>FE: 장소 상세 정보
    FE-->>User: 장소 상세 화면

    User->>FE: 북마크 추가
    FE->>Django: POST /api/v1/places/{id}/bookmarks/
    Django->>DB: Bookmark 생성 (중복 시 409)
    Django-->>FE: 201 Created
    FE-->>User: 북마크 완료

    User->>FE: 리뷰 목록 확인
    FE->>Django: GET /api/v1/places/{id}/reviews
    Django->>DB: 리뷰 목록 조회 (-id 정렬, 페이지네이션)
    Django-->>FE: count + avg_rating + results
    FE-->>User: 리뷰 목록 표시

    User->>FE: 리뷰 작성
    FE->>Django: POST /api/v1/places/{id}/reviews (multipart)
    Django->>DB: Review 저장 (image_url=null)
    Django->>Redis: upload_review_image 태스크 적재
    Django-->>FE: 201 Created
    FE-->>User: 리뷰 등록 완료 (이미지 비동기 처리)
```

---

## 3. 추천 시스템 흐름

### 3-1. 장소 스타일 벡터 생성 (AI 태깅 파이프라인)

```mermaid
flowchart TD
    A[Tour API 장소 데이터 수집<br/>sync_places] --> B[장소 DB 저장<br/>Place + PlaceImage]
    B --> C[AI 태깅<br/>ai_tag_missing_task - 매일 05:00]
    C --> D{Provider}
    D -->|프로덕션| E[Gemini API<br/>일 20건 / 분 4건]
    D -->|로컬| F[Ollama<br/>로컬 LLM]
    E --> G[style_vector 6차원 생성<br/>PlaceFeature 저장]
    F --> G
    G --> H[HNSW 인덱스<br/>벡터 코사인 유사도 검색용]
```

**style_vector 6차원 구조:**

| 축 | 의미 | 0.0 | 1.0 |
|---|---|---|---|
| [0] activity | 활동성 | 힐링 | 액티브 |
| [1] planning | 계획성 | 즉흥 | 계획적 |
| [2] sociability | 사교성 | 혼자 | 그룹 |
| [3] space | 공간 | 자연 | 도심 |
| [4] experience | 경험 | 문화 | 체험 |
| [5] spending | 지출 | 저예산 | 고예산 |

---

### 3-2. 사용자 선호 벡터 생성 및 추천 흐름 (예정)

```mermaid
sequenceDiagram
    actor User as 사용자
    participant FE as 프론트엔드
    participant Django as Django 서버
    participant DB as PostgreSQL (pgvector)

    User->>FE: 여행 성향 테스트 응답
    FE->>Django: POST /api/v1/users/me/preference (6축 가중치)
    Django->>DB: UserFeature.preference_vector 저장 [6차원]
    Django-->>FE: 저장 완료

    User->>FE: 장소 추천 요청
    FE->>Django: GET /api/v1/places/recommend
    Django->>DB: Stage 1 - is_active=True 필터
    Django->>DB: Stage 2 - CosineDistance(style_vector, preference_vector)<br/>HNSW 인덱스로 ANN 검색 → 상위 20개
    Note over Django,DB: 사용자 벡터 없으면 Fallback:<br/>rating_avg DESC, bookmark_count DESC
    Django-->>FE: 추천 장소 목록
    FE-->>User: 맞춤 여행지 표시
```

> **현재 상태**: `PlaceFeature.style_vector` 및 AI 태깅 완료.
> `UserFeature.preference_vector` 및 `/api/v1/places/recommend` 엔드포인트는 구현 예정입니다.

---

## 4. Celery Worker 태스크 흐름

### 3-1. 리뷰 이미지 업로드 (사용자 트리거)

```mermaid
sequenceDiagram
    participant Django as Django 서버
    participant Redis as Redis (Broker)
    participant CW as Celery Worker
    participant S3 as AWS S3
    participant DB as PostgreSQL

    Django->>Redis: upload_review_image.delay(review_id, image_data, content_type)
    Note over Redis: 태스크 큐 대기
    CW->>Redis: 태스크 수신
    CW->>CW: Pillow로 이미지 압축 (≤10MB)<br/>JPEG: quality 루프 / PNG: lossless
    CW->>S3: 압축된 이미지 업로드
    S3-->>CW: 업로드 완료 + S3 URL
    CW->>DB: review.image_url 업데이트
```

> 실패 시 `image_url`은 `null`로 유지됩니다.

---

## 4. Celery Beat 스케줄 태스크 흐름

### 4-1. 장소 데이터 증분 동기화 (매월 1일 04:00)

```mermaid
sequenceDiagram
    participant CB as Celery Beat
    participant Redis as Redis (Broker)
    participant CW as Celery Worker
    participant TourAPI as Tour API (한국관광공사)
    participant DB as PostgreSQL

    Note over CB: 매월 1일 04:00 스케줄 실행
    CB->>Redis: sync_incremental_task 태스크 적재
    CW->>Redis: 태스크 수신
    CW->>TourAPI: areaBasedSyncList2 변경분 조회
    TourAPI-->>CW: 신규·변경·삭제 장소 데이터
    CW->>DB: 신규 장소 생성 / 변경 갱신 / showflag=0 소프트삭제
    Note over CW: 완료 로그: 생성·갱신·미변경·삭제 건수
```

### 4-2. AI 태그 자동 부여 (매일 05:00)

```mermaid
sequenceDiagram
    participant CB as Celery Beat
    participant Redis as Redis (Broker)
    participant CW as Celery Worker
    participant Gemini as Google Gemini API
    participant DB as PostgreSQL

    Note over CB: 매일 05:00 스케줄 실행
    CB->>Redis: ai_tag_missing_task 태스크 적재
    CW->>Redis: 태스크 수신
    CW->>DB: 미태깅 장소 조회 (일 한도 20개)
    loop 분당 최대 4건
        CW->>Gemini: 장소 정보 전송 → 태그 추천 요청
        Gemini-->>CW: 추천 태그 반환
        CW->>DB: 장소에 태그 저장
    end
```

---

## 5. Celery Worker vs Celery Beat 요약

| 구분 | 역할 | 트리거 | 태스크 |
|---|---|---|---|
| **Celery Worker** | 큐에서 태스크를 꺼내 실행 | Django `.delay()` 호출 또는 Beat 적재 | `upload_review_image` |
| **Celery Beat** | 주기적으로 태스크를 큐에 적재 | cron 스케줄 | `sync_incremental_task` (월 1회), `ai_tag_missing_task` (일 1회) |

> **핵심 차이**: Beat는 "언제 실행할지" 결정, Worker는 "실제로 실행"합니다.
> Beat가 없으면 스케줄 태스크는 실행되지 않고, Worker가 없으면 큐에 쌓이기만 합니다.
