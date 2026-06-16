from typing import Any

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q, QuerySet

TRGM_THRESHOLD = 0.15  # pg_trgm 유사도 폴백 임계값 (PG 기본값 0.3보다 낮게 — 한국어 짧은 키워드 대응)

# 장소/지역 유형 접미사 — 길이 내림차순으로 longest-match 보장
_PLACE_TYPE_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        (
            "해수욕장",
            "박물관",
            "미술관",
            "전시관",
            "체험관",
            "과학관",
            "기념관",
            "터미널",
            "경기장",
            "수영장",
            "테마파크",
            "공원",
            "광장",
            "거리",
            "마을",
            "시장",
            "해변",
            "항구",
            "대로",
            "역",
            "항",
            "산",
            "강",
            "천",
            "로",
            "길",
        ),
        key=len,
        reverse=True,
    )
)
_CONNECTOR_PARTICLES = ("에서", "의", "에")  # 조사 — 길이 내림차순


def extract_core_keyword(keyword: str) -> str | None:
    """조사+접미사 패턴에서 핵심어를 추출한다.

    조사(의/에/에서)가 있을 때만 추출 — 조사 없는 직접 합성어("서울역", "남산공원")는
    원본 자체가 검색 대상이므로 확장하지 않는다.

    "가야의거리" → "가야"
    "속초의해수욕장" → "속초"
    "서울역" → None
    """
    for suffix in _PLACE_TYPE_SUFFIXES:
        if keyword.endswith(suffix) and len(keyword) > len(suffix):
            core = keyword[: -len(suffix)]
            for particle in _CONNECTOR_PARTICLES:
                if core.endswith(particle):
                    core = core[: -len(particle)]
                    if len(core) >= 2 and core != keyword:
                        return core
                    break
    return None


def apply_trigram_filter(queryset: QuerySet[Any], field: str, keyword: str) -> QuerySet[Any]:
    """trgm 폴백 — 오타 허용 유사도 필터를 적용한다."""
    return queryset.annotate(trgm_sim=TrigramSimilarity(field, keyword)).filter(trgm_sim__gt=TRGM_THRESHOLD)  # type: ignore[no-any-return]


def build_keyword_q(keyword: str, *field_names: str) -> Q:
    """keyword와 핵심어 추출 결과를 OR로 묶은 Q를 반환한다.

    field_names: icontains 검색을 적용할 필드들 (e.g. "title", "region_tag__tag_name")
    """
    core = extract_core_keyword(keyword)
    q = Q()
    for field in field_names:
        q |= Q(**{f"{field}__icontains": keyword})
        if core:
            q |= Q(**{f"{field}__icontains": core})
    return q
