# 장소 검색 기능 명세

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
| `keyword` | string | `""` | 장소명 부분 일치 검색 |
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

## `/places/search` — 키워드 검색

장소명 키워드로 검색합니다. `keyword` 없이 호출하면 전체 목록과 동일하게 동작합니다.

### 요청 예시

```
GET /api/v1/places/search?keyword=해수욕장&sort=rating&order=desc&page=1&page_size=8
```

### 동작 흐름

```
sort == "recommend"?
├── Yes → get_place_list_recommend(user_id, keyword)
│         ├── 로그인 + 퀴즈 완료 → 벡터 기반 ANN 검색 후 Python in-memory keyword 필터
│         └── 비로그인 / 퀴즈 미완료 → 인기순 폴백 후 Python in-memory keyword 필터
└── No  → get_place_list(keyword, sort, order)
          └── place_name__icontains DB 쿼리 → 정렬 → 페이지네이션
```

---

## `/places/filter` — 태그 필터 + 키워드 검색

태그 ID를 AND 조건으로 필터링합니다. `keyword`와 함께 사용할 수 있습니다.

### 추가 쿼리 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `tags` | int (복수) | 필터링할 태그 ID. AND 조건 |

- 반복 형식: `?tags=1&tags=37`
- 콤마 형식: `?tags=1,37`
- 두 형식 혼용 가능

### 요청 예시

```
GET /api/v1/places/filter?tags=1&tags=37&keyword=해수욕장&sort=recommend
```

### 동작 흐름

```
sort == "recommend"?
├── Yes → get_place_list_recommend(user_id, keyword, tags)
│         ├── 벡터 검색 시 tag_ids를 pgvector 쿼리에 pre-filter로 전달
│         └── keyword는 벡터 검색 결과에서 Python in-memory 필터링
└── No  → get_place_list(keyword, sort, order, tags)
          └── 태그마다 .filter(tags__id=tag_id) 체이닝 (AND 매칭)
              └── place_name__icontains + 정렬 → 페이지네이션
```

### 태그 AND 조건 구현 방식

태그마다 `.filter()`를 체이닝해 각 태그에 대한 별도 JOIN을 생성합니다.
`bookmark_count`는 `Count("bookmarks", distinct=True)`로 집계해 M2M JOIN 곱연산에 의한 값 부풀림을 방지합니다.

```python
for tag_id in tag_ids:
    queryset = queryset.filter(tags__id=tag_id)
```

---

## recommend 정렬 상세

### 벡터 기반 ANN 검색 (로그인 + 퀴즈 완료)

1. `UserTestResult`에서 사용자의 `result_vector` (6차원) 조회
2. `PlaceFeature.style_vector`와 코사인 유사도 계산
3. pgvector HNSW 인덱스 (`m=16`, `ef_construction=64`, `vector_cosine_ops`) 활용
4. `hnsw.iterative_scan = strict_order` 설정으로 tag 필터 시 under-recall 방지
5. M2M JOIN 중복 제거 후 거리 순서 복원 → 상위 N개 반환

### 인기순 폴백 (비로그인 / 퀴즈 미완료)

- `bookmark_count DESC`, `rating_avg DESC` 정렬
- 태그·keyword 필터 없는 경우 Redis에 300초 캐시

### keyword 와 recommend 혼용 시

벡터 검색은 DB 쿼리셋이 아닌 Python 리스트를 반환하므로 keyword 필터를 DB에서 처리할 수 없습니다.
이 때문에 `fetch_limit=100`으로 충분한 후보를 먼저 확보한 뒤 Python 레벨에서 필터링합니다.

```python
fetch_limit = 100 if keyword else 20
places = get_places_sorted_by_vector(...)  # 최대 100개 가져옴
places = [p for p in places if keyword.lower() in p.place_name.lower()]
```

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

## 관련 파일

| 파일 | 역할 |
|------|------|
| `apps/place/views/place_views.py` | `PlaceSearchView`, `PlaceFilterView` |
| `apps/place/services/place_services.py` | `get_place_list()`, `get_place_list_recommend()` |
| `apps/place/services/sort_algorithm_service.py` | `get_places_sorted_by_vector()`, `get_popular_places()` |
| `apps/place/schemas/place_schemas.py` | OpenAPI 스키마 (`place_search_schema`, `place_filter_schema`) |
