트러# 장소 검색 기능 명세

---

## 엔드포인트

| 메서드 | 엔드포인트 | 인증 | 설명 |
|--------|-----------|:---:|------|
| GET | `/api/v1/places/search` | ✗ | 키워드 검색 |
| GET | `/api/v1/places/filter` | ✗ | 태그 필터 + 키워드 검색 |

---

## 공통 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `keyword` | string | `""` | 장소명·태그명 부분 일치 검색 |
| `sort` | string | `bookmark` | 정렬 기준 (아래 표 참고) |
| `order` | string | `desc` | 정렬 방향 (`desc` / `asc`) |
| `page` | int | `1` | 페이지 번호 |
| `page_size` | int | `8` | 페이지당 반환 수 (최대 100) |

### sort 옵션

| 값 | 정렬 기준 | 비고 |
|----|----------|------|
| `bookmark` | 북마크 수 내림차순 | 기본값 |
| `review` | 리뷰 수 내림차순 | `rating_count` 비정규화 컬럼 사용 |
| `rating` | 평점 내림차순 | |
| `recommend` | 퀴즈 성향 벡터 기반 유사도 순 | `order` 파라미터 무시, 비로그인/퀴즈 미완료 시 인기순 폴백 |

---

## 검색 아키텍처 — 3계층 키워드 검색

`keyword`가 있을 때 아래 순서로 계층을 시도하며, **앞 계층에 결과가 있으면 다음 계층을 시도하지 않는다.**

```
1계층 (name/tag/핵심어)
  place_name ILIKE %keyword%
  OR tags.tag_name ILIKE %keyword%
  OR place_name ILIKE %core%          ← 조사+접미사가 있을 때만
          │
          │ 결과 없음
          ▼
2계층 (address)
  address_primary ILIKE %keyword%     ← "가야의거리" → 가야 거리에 위치한 장소
          │
          │ 결과 없음
          ▼
3계층 (trgm 폴백)
  TrigramSimilarity(place_name, keyword) > 0.15   ← 오타 허용
```

### 설계 의도

- **1·2계층 분리**: "가야의거리" 검색 시 1계층에서 "가야의거리"·"가야" 이름 매칭이 되면 주소에 "가야" 포함된 무관 장소(예: 미술의거리)가 섞이지 않는다.
- **trgm 폴백**: "한라샨" → "한라산" 같은 오타를 pg_trgm 유사도(`TRGM_THRESHOLD = 0.15`)로 처리.

---

## 핵심어 추출 (`_extract_core_keyword`)

`keyword`에 **조사(의/에/에서) + 장소 접미사**가 함께 있을 때만 핵심어를 추출한다.

```
"가야의거리"    → "가야"   (조사 "의" + 접미사 "거리" 제거)
"속초의해수욕장" → "속초"  (조사 "의" + 접미사 "해수욕장" 제거)
"서울역"        → None    (조사 없음 → 확장 안 함)
"남산공원"      → None    (조사 없음 → 확장 안 함)
"대학로"        → None    (조사 없음 → 확장 안 함)
```

**조사 없는 직접 합성어(`서울역`, `남산공원`)는 그 자체가 검색 대상이므로 확장하지 않는다.**
조사가 있을 때만 확장하면, `서울역` → `서울`처럼 수백 개의 서울 장소가 함께 나오는 과-확장을 방지할 수 있다.

지원 접미사는 길이 내림차순으로 정렬(longest-match)하며, 짧은 접미사가 긴 접미사의 일부를 잘못 제거하는 것을 방지한다.

```python
_PLACE_TYPE_SUFFIXES = tuple(sorted((...), key=len, reverse=True))
_CONNECTOR_PARTICLES = ("에서", "의", "에")   # 길이 내림차순
```

---

## 1계층 내 관련성 정렬 (`_relevance`)

1계층 매칭 시 단순 인기도순이 아닌 **관련성 우선** 정렬을 적용한다.

| `_relevance` 값 | 조건 |
|----------------|------|
| 2 | `place_name ILIKE %keyword%` 또는 `tag_name ILIKE %keyword%` (정확 매칭) |
| 1 | `place_name ILIKE %core%` (핵심어 확장 매칭) |
| 0 | 그 외 |

정렬 순서: `_relevance DESC` → 요청 `sort` 기준 → `id DESC` (페이지네이션 결정성 보장)

"가야의거리" 검색 시 "가야의거리" 이름을 가진 장소가 "가야"를 이름에 포함한 장소보다 앞에 온다.

---

## `exists()` 제거 — 단일 annotation pass

이전에는 계층별 `exists()` 체크 + 데이터 쿼리로 최대 3 queries가 발생했다.
현재는 `CASE WHEN` annotation + `aggregate(Min(_tier))`으로 2 queries로 줄였다.

```python
annotated = queryset.annotate(
    _tier=Case(When(tier1_q, then=1), When(addr_q, then=2), default=99),
    _relevance=Case(When(exact_q, then=2), When(core_q, then=1), default=0),
).filter(_tier__lt=99).distinct()

best_tier = annotated.aggregate(best_tier=Min("_tier"))["best_tier"]  # query 1
queryset  = annotated.filter(_tier=best_tier)                         # query 2 (paginator)
```

---

## Hybrid Search (`sort=recommend` + `keyword`)

로그인 + 퀴즈 완료 + keyword 있는 경우, DB keyword 필터와 벡터 유사도를 결합한 하이브리드 스코어로 정렬한다.

### 처리 흐름

```
1) 3계층 keyword 필터로 후보 ID 수집 (최대 HYBRID_CANDIDATE_LIMIT=200)
2) 후보에 대해서만 정확 코사인 유사도 계산 (HNSW 미사용 — exact scan)
3) combined score = 0.7 × vec_score + 0.3 × kw_score
4) 정렬 후 Place 객체 로드
```

### 스코어 계산

```python
vec_score = 1.0 - CosineDistance / 2.0   # [0,2] → [0,1] 정규화
                                           # PlaceFeature 없으면 중립값 0.5
kw_score  = TrigramSimilarity(place_name, keyword)
            # exact 매칭(1·2계층)은 kw_score = max(trgm, 0.3) 보장

combined  = 0.7 × vec_score + 0.3 × kw_score
```

### 캐싱

동일 `(keyword, tags, user_vector)` 조합의 sorted ID 목록을 **5분(300초)** Django cache에 저장한다.
캐시 키: `hybrid_ids:{MD5(keyword|tags|vector_4dp)}`

캐시 히트 시 벡터 계산·trgm 계산 쿼리를 건너뛰고 ID 목록으로 Place 객체만 로드한다.

---

## 인기순 폴백 in-memory 필터 (`sort=recommend`, 비로그인/퀴즈 미완료)

DB 경로 3계층과 동일한 우선순위를 in-memory에서도 적용한다.

```python
# Tier 1: 이름·태그·핵심어 매칭
tier1 = [p for p in places if name_or_tag_or_core_matches(p)]
# Tier 2: 주소 매칭 (tier1 결과가 없을 때만)
places = tier1 or [p for p in places if address_matches(p)]
```

이전에는 주소가 항상 OR 조건으로 포함되어 이름 매칭 결과와 주소 매칭 결과가 섞였다.

---

## recommend 정렬 상세

### 벡터 기반 ANN 검색 (로그인 + 퀴즈 완료)

1. `UserTestResult`에서 사용자의 `result_vector` (6차원) 조회
2. 영벡터(`all(v == 0)`)는 코사인 유사도 미정의 → 인기순 폴백으로 처리
3. `PlaceFeature.style_vector`와 HNSW 인덱스로 ANN 검색
4. `hnsw.iterative_scan = strict_order` 설정으로 tag 필터 시 under-recall 방지

### 인기순 폴백 (비로그인 / 퀴즈 미완료)

- `bookmark_count DESC`, `rating_avg DESC` 정렬
- 태그·keyword 필터 없는 경우 Redis에 300초 캐시

---

## 응답 형식

```json
{
  "count": 42,
  "next": "http://.../api/v1/places/search?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "place_name": "광안리 해수욕장",
      "image_url": "https://example.com/image.jpg",
      "description": "부산을 대표하는 해수욕장입니다.",
      "latitude": 35.1531696,
      "longitude": 129.118666,
      "bookmark_count": 150,
      "is_bookmarked": true,
      "rating_avg": 4.5,
      "tags": [
        {"id": 1, "tag_name": "해변"},
        {"id": 37, "tag_name": "부산"}
      ]
    }
  ]
}
```

- `is_bookmarked`: 로그인 사용자 기준. 비로그인 시 항상 `false`

---

## 코드 리뷰 수정 이력

### 1차 코드 리뷰 (feat/search_upgrade 브랜치 초기)

#### HIGH

| # | 문제 | 수정 내용 |
|---|------|----------|
| H1 | `address_primary__icontains` 가 1계층 name/tag 와 OR로 묶여 "미술의거리" 같은 무관 장소가 노출 | `address_primary`를 2계층 폴백으로 분리 |
| H2 | `vec_score = 1.0 - dist` 로 계산 — CosineDistance 범위 [0,2]를 [0,1]로 가정한 버그 | `vec_score = 1.0 - dist / 2.0` 으로 정규화 |
| H3 | trgm 후보 200개를 `rating_avg` 정렬 없이 임의 순서로 cap | `.order_by("-rating_avg")` 추가 |
| H4 | migration `0013_enable_pg_trgm.py`에 `atomic = False` 누락 — AWS RDS 등 일부 PG 환경에서 트랜잭션 내 `CREATE EXTENSION` 실패 | `atomic = False` 추가 |

#### MEDIUM

| # | 문제 | 수정 내용 |
|---|------|----------|
| M1 | `_PLACE_TYPE_SUFFIXES` 순서가 주석으로만 보장 — 런타임에 검증 없음 | `tuple(sorted(..., key=len, reverse=True))` 로 프로그래밍 정렬 |
| M2 | trgm 폴백에서 `trgm_sim` 값을 `kw_map` 계산 시 다시 쿼리 | `prefetched_kw_map` 에 저장 후 재사용 |
| M3 | PlaceFeature 없는 장소가 `vec_score = 0.0` (반대 성향) 처리 | 중립값 0.5로 처리 |

#### LOW

| # | 문제 | 수정 내용 |
|---|------|----------|
| L1 | 마이그레이션 롤백 주의사항 문서 없음 | rollback 순서 주석 추가 |
| L2 | `HYBRID_CANDIDATE_LIMIT`, `VEC_WEIGHT` 등 상수 설명 없음 | 각 상수에 인라인 주석 추가 |
| L3 | `kw_map or {}` truthiness 취약 — `prefetched_kw_map`이 빈 dict일 때 불필요한 trgm 쿼리 실행 가능 | `is_trgm_fallback` 명시적 플래그로 교체 |

---

### 2차 코드 리뷰 (계층화 + 핵심어 추출 구현 후)

#### HIGH

| # | 문제 | 수정 내용 |
|---|------|----------|
| H1 | `_extract_core_keyword` 가 조사 없이도 핵심어 추출 — `"서울역"→"서울"`, `"남산공원"→"남산"` 과-확장 | 조사(`의/에/에서`)가 있을 때만 추출하도록 변경 |
| H2 | `_build_name_tag_q` 에서 핵심어 OR 조건이 무조건 추가 — 직접 합성어도 확장됨 | 위 H1 수정으로 함께 해결 (`_extract_core_keyword` 가 None 반환 시 OR 없음) |

#### MEDIUM

| # | 문제 | 수정 내용 |
|---|------|----------|
| M1 | `get_place_list` tier1 내 정확 매칭과 핵심어 매칭이 동일 순위로 섞임 | `_relevance` annotation 추가 — 정확 이름/태그(2) > 핵심어(1) |
| M2 | tier 확인마다 `exists()` 체크 + 데이터 쿼리 = 최대 3 queries | `CASE WHEN` annotation + `aggregate(Min(_tier))` 으로 2 queries로 통합 |
| M3 | hybrid search가 동일 요청을 매 페이지마다 재계산 | sorted ID 목록을 Django cache에 5분 캐시 (`HYBRID_CACHE_TTL=300`) |
| M4 | `kw_map or {}` — `prefetched_kw_map` 이 빈 dict일 때 오른쪽 식이 실행될 수 있음 | `is_trgm_fallback` 명시적 불리언 플래그로 교체 |

#### LOW

| # | 문제 | 수정 내용 |
|---|------|----------|
| L1 | in-memory 폴백 경로(`get_place_list_recommend`)에서 주소가 항상 OR — DB 경로 3계층과 불일치 | tier1(이름/태그/핵심어) 결과 없을 때만 주소 폴백 적용 |
| L2 | `address_primary` null 처리가 in-memory(`p.address_primary and ...`)와 DB(`icontains` → SQL NULL 처리) 간 표현 방식 불일치 | in-memory 경로를 tier1/tier2 분리 구조로 재작성하여 null 처리 일관성 확보 |

---

### 3차 수정 (feat/recommend-sort-full — 추천순 전체 장소 반환)

#### HIGH

| # | 문제 | 수정 내용 |
|---|------|----------|
| H1 | `sort=recommend` 응답에서 결과가 DB 전체 장소 수가 아닌 벡터 보유 장소 수(예: 12개)로 제한됨 | `get_places_sorted_by_vector`에 `limit=None` 지원 추가 후 `_append_remaining`으로 벡터 없는 나머지 장소를 인기순으로 이어 붙임 |

**H1 원인 분석**

```
sort=recommend
 └─ get_place_list_recommend()
      └─ get_places_sorted_by_vector(limit=20)
           └─ PlaceFeature.objects.filter(style_vector__isnull=False)
                                            ↑
                             이 조건 + limit=20으로
                             벡터 있는 장소만 최대 20개 반환
                             → DB에 style_vector 보유 장소가 12개면 12개만 노출
```

진단 쿼리:
```sql
SELECT COUNT(*)
FROM place_placefeature pf
JOIN place_place p ON p.id = pf.place_id
WHERE p.is_active = TRUE AND pf.style_vector IS NOT NULL;
-- 이 값이 실제 응답 count와 일치하면 H1 케이스
```

#### MEDIUM

| # | 문제 | 수정 내용 |
|---|------|----------|
| M1 | S1(비로그인) 추천 결과가 인기순 상위 20개로 제한 — 다른 정렬과 달리 전체 장소를 탐색할 수 없었음 | `get_popular_places(limit=None)` 호출로 전체 인기순 반환 |
| M2 | H1 수정 후 CI 테스트 `test_content_vector_없는_장소는_S3_결과에서_제외` 실패 | 테스트 기댓값을 "제외" → "벡터 결과 뒤에 포함, 순서 보장"으로 수정 |

**M2 실패 패턴** — 동작 변경 시 테스트 기댓값이 구동작 기준으로 남아 CI에서 검출됨

```python
# 변경 전 테스트 (old behavior: 벡터 없는 장소 제외)
assert without_vector.id not in place_ids  # ← 새 동작에서 실패

# 변경 후 테스트 (new behavior: 하단 인기순으로 포함)
assert without_vector.id in place_ids
assert place_ids.index(with_vector.id) < place_ids.index(without_vector.id)
```

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `apps/place/views/place_views.py` | `PlaceSearchView`, `PlaceFilterView` |
| `apps/place/services/place_services.py` | `get_place_list()`, `get_place_list_recommend()`, `_get_places_hybrid()`, `_extract_core_keyword()` |
| `apps/place/services/sort_algorithm_service.py` | `get_places_sorted_by_vector()`, `get_popular_places()` |
| `apps/place/migrations/0013_enable_pg_trgm.py` | pg_trgm extension 설치 (`atomic=False`) |
| `apps/place/migrations/0014_place_name_trgm_gin_index.py` | `place_name` GIN 인덱스 (`gin_trgm_ops`) |
| `apps/place/schemas/place_schemas.py` | OpenAPI 스키마 (`place_search_schema`, `place_filter_schema`) |
| `apps/place/tests/test_place.py` | 검색 통합 테스트 (`TestPlaceRecommendHybridSearch` 등) |
