# 추천순 페이지네이션 프론트 연동 가이드

## 문제 원인

추천순 API가 다른 정렬과 다른 응답 형식을 반환하고 있었음.

| 엔드포인트 | 응답 형식 | 프론트 처리 |
|---|---|---|
| `/places/search?sort=bookmark` 등 | `{ count, next, previous, results }` | `data.results`, `data.count` |
| `/places/recommend` (변경 전) | `[ {place}, ... ]` flat 배열 | `data`, `data.length` |

프론트에서 추천순은 `data.length`를 totalCount로 사용했기 때문에 항상 `limit`개(12개)가 전체 개수로 인식되어 페이지네이션이 동작하지 않았음.

---

## 백엔드 변경 사항 (PR #211)

응답 형식을 다른 정렬과 동일하게 통일.

```
# 변경 전 파라미터
GET /api/v1/places/recommend?limit=12

# 변경 후 파라미터
GET /api/v1/places/recommend?page=1&page_size=12
```

```json
// 변경 전 응답 — flat 배열
[
  { "id": 1, "place_name": "광안리 해수욕장", ... },
  { "id": 2, "place_name": "해운대 해수욕장", ... }
]

// 변경 후 응답 — 페이지네이션
{
  "count": 19980,
  "next": "https://.../places/recommend?page=2&page_size=12",
  "previous": null,
  "results": [
    { "id": 1, "place_name": "광안리 해수욕장", ... },
    { "id": 2, "place_name": "해운대 해수욕장", ... }
  ]
}
```

---

## 프론트 수정 위치

### 1. `src/types/place.types.ts`

```typescript
// 변경 전
export type GetPlacesRecommendParams = {
  tags?: number[]
  region_tag_id?: number
  limit?: number
}

// 변경 후
export type GetPlacesRecommendParams = {
  tags?: number[]
  region_tag_id?: number
  page?: number
  page_size?: number
}
```

### 2. `src/lib/placesApi.ts`

```typescript
// 변경 전
export const getPlacesRecommend = async (
  params: GetPlacesRecommendParams = {}
): Promise<Place[]> => {
  const response = await api.get<Place[]>(PLACES_RECOMMEND_PATH, {
    params,
    paramsSerializer: serializeParams,
  })
  return response.data
}

// 변경 후
export const getPlacesRecommend = async (
  params: GetPlacesRecommendParams = {}
): Promise<PlacesResponse> => {
  const response = await api.get<PlacesResponse>(PLACES_RECOMMEND_PATH, {
    params,
    paramsSerializer: serializeParams,
  })
  return response.data
}
```

### 3. `src/features/explore/hooks/useExplorePlaces.ts`

```typescript
// 변경 전
getPlacesRecommend({
  ...(recommendTagIds.length > 0 ? { tags: recommendTagIds } : {}),
  limit: ITEMS_PER_PAGE,
})
  .then((data) => {
    if (cancelled) return
    setPlaces(data)
    setTotalCount(data.length)
    setFetchedKey(currentKey)
  })

// 변경 후
getPlacesRecommend({
  ...(recommendTagIds.length > 0 ? { tags: recommendTagIds } : {}),
  page: currentPage,
  page_size: ITEMS_PER_PAGE,
})
  .then((data) => {
    if (cancelled) return
    setPlaces(data.results)
    setTotalCount(data.count)
    setFetchedKey(currentKey)
  })
```

---

## 수정 후 동작

- 1페이지: 벡터 유사도 1~12위 장소
- 2페이지: 벡터 유사도 13~24위 장소
- N페이지: 다른 정렬과 동일하게 페이지네이션 동작
- 비로그인/퀴즈 미완료: 인기순 상위 장소로 동일하게 페이지네이션
