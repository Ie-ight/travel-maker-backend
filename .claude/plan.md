# 검색 기능 강화 계획

엔드포인트·응답 형식 변경 없이 `apps/place/services/place_services.py` 중심으로 검색 품질을 개선한다.
작업 전 이 문서를 읽고, 완료된 항목은 `[x]`로 체크하며 업데이트한다.

---

## 구현 순서 요약

| 순서 | 작업 | 난이도 | 효과 |
|------|------|--------|------|
| 1 | 태그명 + 주소 OR 검색 확장 | 낮음 | 즉각적 |
| 2 | pg_trgm 유사도 폴백 | 낮음 | 오타 허용 |
| 3 | Hybrid Search (`sort=recommend` + keyword) | 중간 | 의미 기반 랭킹 |

---

## Phase 1 — 태그명 + 주소 OR 검색 확장

### 목적

현재 keyword 검색은 `place_name__icontains`만 본다.
"캠핑" 검색 시 `tag_name="캠핑"` 인 장소가 누락되고, "강남" 검색 시 주소 기반 결과가 나오지 않는 문제를 해결한다.

### 변경 내용

`get_place_list()` 의 keyword 필터를 OR 조건으로 확장한다.

```python
# 변경 전
if keyword:
    queryset = queryset.filter(place_name__icontains=keyword)

# 변경 후
if keyword:
    queryset = queryset.filter(
        Q(place_name__icontains=keyword) |
        Q(tags__tag_name__icontains=keyword) |
        Q(address_primary__icontains=keyword)
    ).distinct()  # M2M join 중복 제거
```

`get_place_list_recommend()` 의 keyword in-memory 필터도 동일하게 확장한다.

```python
# 변경 전
places = [p for p in places if kw in p.place_name.lower()]

# 변경 후
places = [
    p for p in places
    if kw in p.place_name.lower()
    or any(kw in t.tag_name.lower() for t in p.tags.all())
    or (p.address_primary and kw in p.address_primary.lower())
]
```

단, recommend 경로의 in-memory 필터는 Phase 3 이후 hybrid로 대체되므로 임시 처리다.

### 수정 파일

- `apps/place/services/place_services.py`

### 체크리스트

- [x] `get_place_list()` OR 필터 적용
- [x] `get_place_list_recommend()` in-memory 필터 확장
- [x] 테스트: `apps/place/tests/test_place.py` 케이스 추가 및 기존 케이스 수정
- [x] 테스트 통과 확인 (85/85 passed)

---

## Phase 2 — pg_trgm 유사도 폴백

### 목적

keyword 검색 결과가 0건일 때 pg_trgm 유사도 검색으로 폴백해 오타·유사 표현을 허용한다.
"해수욕" → "해수욕장", "광안리해수" → "광안리 해수욕장" 등.

### 사전 작업: 마이그레이션 1개

```python
# apps/place/migrations/XXXX_add_pg_trgm.py
from django.contrib.postgres.operations import TrigramExtension

class Migration(migrations.Migration):
    operations = [TrigramExtension()]
```

### 변경 내용

`get_place_list()` 에 폴백 로직 추가.

```python
from django.contrib.postgres.search import TrigramSimilarity

def get_place_list(keyword="", sort="bookmark", order="desc", ...):
    queryset = Place.objects.filter(is_active=True)...

    if keyword:
        exact_qs = queryset.filter(
            Q(place_name__icontains=keyword) |
            Q(tags__tag_name__icontains=keyword) |
            Q(address_primary__icontains=keyword)
        ).distinct()

        if exact_qs.exists():
            queryset = exact_qs
        else:
            # 결과 없으면 trgm 유사도 폴백 (임계값 0.15~0.2 사이 튜닝 필요)
            queryset = queryset.annotate(
                sim=TrigramSimilarity("place_name", keyword)
            ).filter(sim__gt=0.15).order_by("-sim")
    ...
```

### 수정 파일

- `apps/place/migrations/XXXX_add_pg_trgm.py` (신규)
- `apps/place/services/place_services.py`

### 체크리스트

- [ ] `TrigramExtension` 마이그레이션 생성 및 적용
- [ ] `get_place_list()` 폴백 로직 추가
- [ ] 임계값 0.15 기준으로 테스트 후 조정
- [ ] 테스트: 오타 입력 케이스 추가

---

## Phase 3 — Hybrid Search (`sort=recommend` + keyword 충돌 해결)

### 현재 문제

`sort=recommend` + keyword 조합 시 순서가 잘못되어 있다.

```
현재 흐름:
  HNSW ANN 검색 (벡터 기준 상위 100개 추출)
        ↓
  Python에서 keyword 필터 (place_name icontains만)

문제: 벡터 기준 상위 100개 안에 keyword 매칭 장소가 없으면 결과가 0건
```

### 해결 방향

keyword 있을 때는 순서를 뒤집어, **keyword로 먼저 후보를 추린 뒤** 그 안에서 벡터 유사도를 exact 계산해 합산한다.
HNSW를 사용하지 않지만 keyword 후보 수가 수십~수백 개 수준이라 exact cosine으로도 충분히 빠르다.

```
Hybrid 흐름 (keyword 있을 때):
  keyword로 후보 추리기 (place_name + tag_name + address OR + trgm 폴백)
        ↓
  후보에 대해 cosine 유사도 exact 계산 (HNSW 미사용)
        ↓
  vec_score(0~1) + kw_score(trgm, 0~1) 가중합 → 정렬

keyword 없을 때:
  기존 HNSW ANN 경로 유지 (변경 없음)
```

### 변경 내용

`get_place_list_recommend()` 를 keyword 유무에 따라 분기한다.

```python
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import F
from pgvector.django import CosineDistance

def get_place_list_recommend(user_id, keyword="", tags=None):
    user_vector = _get_user_vector(user_id)  # UserTestResult 조회, 없으면 None

    # keyword 없으면 기존 HNSW 경로 유지
    if not keyword:
        if user_vector:
            return get_places_sorted_by_vector(user_vector, tag_ids=tags, limit=20)
        return get_popular_places(tag_ids=tags, limit=20)

    # keyword 있으면 Hybrid 경로
    return _get_places_hybrid(user_vector, keyword=keyword, tag_ids=tags)


def _get_places_hybrid(user_vector, keyword, tag_ids=None, limit=20):
    # 1. keyword로 후보 추리기 (style_vector 있는 장소만)
    qs = Place.objects.filter(is_active=True, place_feature__isnull=False)
    exact_qs = qs.filter(
        Q(place_name__icontains=keyword) |
        Q(tags__tag_name__icontains=keyword) |
        Q(address_primary__icontains=keyword)
    ).distinct()

    # exact 결과 없으면 trgm 폴백
    if not exact_qs.exists():
        qs = qs.annotate(sim=TrigramSimilarity("place_name", keyword)).filter(sim__gt=0.15)
    else:
        qs = exact_qs

    if tag_ids:
        for tag_id in tag_ids:
            qs = qs.filter(tags__id=tag_id)

    # 2. 벡터 유사도 + keyword 유사도 동시 계산
    if user_vector:
        qs = qs.annotate(
            vec_score=1 - CosineDistance("place_feature__style_vector", user_vector),
            kw_score=TrigramSimilarity("place_name", keyword),
        ).annotate(
            combined=0.7 * F("vec_score") + 0.3 * F("kw_score")
        ).order_by("-combined")
    else:
        # 벡터 없으면 keyword 유사도 + 인기순 폴백
        qs = qs.annotate(
            kw_score=TrigramSimilarity("place_name", keyword),
            bookmark_count=Count("bookmarks", distinct=True),
        ).order_by("-kw_score", "-bookmark_count")

    return list(qs.prefetch_related("images", "tags")[:limit])
```

### 가중치 기준

| 상황 | vec_score | kw_score |
|------|-----------|----------|
| 기본 (취향 우선) | 0.7 | 0.3 |
| 검색 의도가 강할 때 | 0.4 | 0.6 |
| 벡터 없음 (퀴즈 미완료) | — | 인기순 폴백 |

가중치는 추후 A/B 테스트로 조정 가능하도록 상수로 분리한다.

### 수정 파일

- `apps/place/services/place_services.py` (`get_place_list_recommend`, `_get_places_hybrid` 추가)

### 체크리스트

- [ ] `_get_places_hybrid()` 함수 구현
- [ ] `get_place_list_recommend()` 분기 로직 수정
- [ ] keyword 없는 경우 기존 HNSW 경로 회귀 테스트
- [ ] keyword + recommend 조합 테스트 (결과 0건 케이스 포함)
- [ ] 비로그인 + keyword + recommend 케이스 테스트

---

## 전체 수정 파일 목록

| 파일 | Phase |
|------|-------|
| `apps/place/services/place_services.py` | 1, 2, 3 |
| `apps/place/migrations/XXXX_add_pg_trgm.py` | 2 |
| `apps/place/tests/` (기존 또는 신규) | 1, 2, 3 |

스키마(`place_schemas.py`)와 뷰(`place_views.py`)는 변경하지 않는다.

---

## 참고

- pg_trgm 임계값: 한국어는 자모 단위 트라이그램이라 영어보다 낮게 설정 (0.15~0.2 권장)
- Hybrid 가중치: `VEC_WEIGHT = 0.7`, `KW_WEIGHT = 0.3` 상수로 분리해 추후 튜닝
- `_get_places_hybrid()` 는 Phase 2 완료 후 구현 (pg_trgm 마이그레이션 선행 필요)
