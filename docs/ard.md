# 장소 목록 조회와 검색 엔드포인트 분리 여부

- **상태(Status)**: 🟡 보류 (Deferred) — 검색 로드맵이 구체화되면 재논의
- **날짜**: 2026-05-31
- **관련 코드**: `apps/place/views/place_views.py`(`PlaceListView`, `PlaceSearchView`), `apps/place/services/place_services.py`(`get_place_list`), `apps/place/urls.py`

## 배경(Context)

현재 장소 도메인에는 두 개의 엔드포인트가 있다.

- `GET /api/v1/places/` — 목록 조회 (`PlaceListView`)
- `GET /api/v1/places/search` — 검색 (`PlaceSearchView`)

그런데 검색은 사실상 **"목록 + `place_name__icontains` 필터 + 정렬"** 일 뿐이다. 두 뷰가
- **같은 서비스** `get_place_list(keyword, sort, order)` 를 호출하고,
- **같은 직렬화기** `PlaceListSerializer` 로 **100% 동일한 응답**을 낸다.

이 중복은 "검색이 사실은 필터 걸린 목록"이라는 신호이고, "목록과 검색을 분리하는 게 맞나?"라는 의문으로 이어졌다.

추가로, 검색어가 비었을 때의 동작(전체 목록 vs 400)을 두고 고민이 있었는데, 이 어색함 자체가 `/search` 가 목록과 다를 게 없다는 증상이기도 했다.

## 선택지(Options)

### 패턴 A — 하나의 컬렉션 엔드포인트 + 쿼리파라미터 (REST/DRF 주류)

```
GET /api/v1/places/?keyword=서울&sort=review&order=desc&page=1
```

- 목록 = 검색. 필터·검색·정렬·페이지네이션이 전부 컬렉션의 쿼리파라미터.
- `PlaceListView` 가 이미 `get_place_list()` 를 호출하므로, 거기서 `keyword`/`sort`/`order` 를 읽게 하고 `PlaceSearchView` + URL 을 제거하면 됨.
- **장점**: 중복 제거, 일관된 페이지네이션/정렬, "키워드 없음 = 필터 없음 = 둘러보기"가 자연스러워 400 딜레마가 사라짐.
- **단점**: 검색이 단순 필터 이상으로 커지면(전문검색/관련도) 한 뷰가 비대해질 수 있음.

### 패턴 B — 별도 `/search` 엔드포인트 (현행 유지)

- 검색이 *진짜 다른 기능* 일 때 적합: 전문(full-text) 검색, 관련도 스코어링, Elasticsearch/OpenSearch 등 별도 저장소, 다른 응답(하이라이트·score), POST + 복잡한 쿼리 바디, 별도 rate-limit/캐싱.
- 이 경우 **검색어 필수(빈 검색어 → 400)** 가 일관된 정책이 됨.
- 예: GitHub `/repos`(목록) vs `/search/repositories`(검색)는 별개 서브시스템.

## 결정의 분기점

> 검색이 앞으로도 **"이름으로 필터"** 에 머무를 것인가, 아니면 **진짜 검색(full-text / 관련도 / AI 추천)** 으로 키울 것인가?

- 단순 필터에 머무름 → **패턴 A(목록에 통합)** 가 정석
- 진짜 검색으로 발전 → **패턴 B(분리 유지)** + 검색어 필수(400)

CLAUDE.md 의 "AI 기반 여행 추천" 방향과 Postgres `trigram`/`SearchVector` 또는 Elasticsearch 도입 가능성이 이 판단의 핵심 변수다.

## 결정(Decision)

**보류.** 검색 기능의 로드맵(단순 필터 유지 vs 전문검색/AI 확장)이 확정되기 전까지 결정하지 않는다.

그때까지 **현행(패턴 B, 분리 유지)** 을 그대로 둔다:
- `GET /api/v1/places/` (목록) 와 `GET /api/v1/places/search` (검색) 공존
- 빈/누락 검색어 → 전체 목록 반환 (400 아님)
- 두 뷰 모두 `get_place_list()` 공유

## 영향(Consequences)

- (현행 유지 동안) 검색과 목록의 코드 중복이 일부 남는다. 단, 서비스/직렬화기를 공유하므로 비용은 작다.
- 추후 패턴 A 로 합치기로 하면: `PlaceListView` 에 쿼리파라미터를 흡수하고 `PlaceSearchView`/URL/관련 테스트를 정리하면 된다. 마이그레이션 부담 없음(URL 계약만 변경).
- 추후 패턴 B 를 확정하면: 검색어 필수(400) 정책을 도입한다. 이때 `core/exception_handler.py` 가 dict 응답을 가정하므로 `ValidationError("문자열")`(→ 리스트 → 500 유발)은 피하고, `Response({"error_detail": ...}, status=400)` 또는 `ParseError` 를 써야 한다.
