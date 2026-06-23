# 추천순(sort=recommend) 동작 방식

## 변경 전 vs 변경 후

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 반환 장소 수 | 벡터 있는 장소 최대 20개 | 전체 장소 (페이지네이션으로 분할) |
| 벡터 없는 장소 | 결과에서 제외 | 벡터 결과 뒤에 인기순으로 노출 |
| S1(비로그인) no keyword | 인기순 상위 20개 | 전체 장소 인기순 |

---

## 단계별 동작

### S1 — 비로그인 / 퀴즈 미완료

```
keyword 없음  →  전체 장소를 북마크↓ · 평점↓ · 조회수↓ 순으로 반환
keyword 있음  →  인기순 상위 100개 중 keyword 매칭 필터링 (기존과 동일)
```

### S2 — 퀴즈 완료 (6축 style_vector)

```
keyword 없음  →  [style_vector 있는 장소 전체, 코사인 유사도 높은 순]
                  + [style_vector 없는 나머지 장소, 인기순]
keyword 있음  →  keyword 매칭 후 combined score 정렬 (0.7 × 벡터 + 0.3 × 키워드)
```

### S3 — 행동 기반 임베딩 (1024D content_vector)

```
keyword 없음  →  [content_vector 있는 장소 전체, 코사인 유사도 높은 순]
                  + [content_vector 없는 나머지 장소, 인기순]
keyword 있음  →  S2와 동일 방식, content_vector 사용
```

---

## 핵심 함수 흐름

```
GET /api/v1/places/search?sort=recommend
       │
       ▼
PlaceSearchView.get()
       │  sort == "recommend"
       ▼
get_place_list_recommend(user_id, keyword, tags)
       │
       ├─ determine_stage(user_id)  →  S1 / S2 / S3
       │
       ├─ [S2/S3, no keyword]
       │       get_places_sorted_by_vector(limit=None)   ← 전체 fetch
       │       _append_remaining(vector_places, tags)    ← 나머지 인기순 이어 붙임
       │
       ├─ [S2/S3, keyword]
       │       _get_places_hybrid()   ← combined score 정렬 (기존과 동일)
       │
       └─ [S1, no keyword]
               get_popular_places(limit=None)            ← 전체 인기순
       │
       ▼
CustomPagination (page_size=8)
```

---

## `_append_remaining` 동작

```python
# 벡터 정렬된 장소 ID를 제외한 나머지를 인기순으로 쿼리
Place.objects.filter(is_active=True)
    .exclude(id__in=vector_ids)
    .order_by("-bookmark_count", "-rating_avg", "-view_count")
```

태그 필터가 있으면 나머지 쿼리에도 동일하게 적용된다.

---

## 주의사항

- `get_places_sorted_by_vector(limit=None)` 호출 시 `_OVER_FETCH` 슬라이싱을 건너뛰고 전체 `PlaceFeature` 레코드를 순회한다. DB 장소 수가 매우 많아지면 성능 모니터링이 필요하다.
- `get_popular_places(limit=None)` 은 Redis 캐싱을 건너뛴다 (limit 있는 경우만 캐싱).
