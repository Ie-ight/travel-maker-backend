"""PlaceFeature 덤프/적재 — 환경(로컬 ↔ 배포) 간 이전용.

place_id(PK)는 환경마다 다를 수 있으므로 Tour API 고유값인 Place.content_id를
매칭 키로 사용한다.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypedDict

from apps.place.models import Place, PlaceFeature


class PlaceFeatureRow(TypedDict):
    content_id: int
    style_vector: list[float] | None
    content_vector: list[float] | None


@dataclass
class LoadSummary:
    matched: int
    unmatched: int


#: 코사인 유사도에 충분한 정밀도를 유지하면서 JSON 덤프 용량을 줄이기 위한 소수점 자리수
_VECTOR_PRECISION = 6


def _round_vector(vector: Iterable[float]) -> list[float]:
    return [round(float(v), _VECTOR_PRECISION) for v in vector]


def serialize_place_features(queryset: Iterable[PlaceFeature]) -> list[PlaceFeatureRow]:
    """PlaceFeature 쿼리셋을 content_id 기준 JSON 직렬화 가능한 행 목록으로 변환한다."""
    rows: list[PlaceFeatureRow] = []
    for feature in queryset:
        rows.append(
            {
                "content_id": feature.place.content_id,
                "style_vector": _round_vector(feature.style_vector) if feature.style_vector is not None else None,
                "content_vector": _round_vector(feature.content_vector) if feature.content_vector is not None else None,
            }
        )
    return rows


def load_place_features(rows: Iterable[PlaceFeatureRow]) -> LoadSummary:
    """content_id로 Place를 찾아 PlaceFeature를 update_or_create한다. content_id 미존재 시 건너뜀."""
    matched = unmatched = 0
    for row in rows:
        place = Place.objects.filter(content_id=row["content_id"]).first()
        if place is None:
            unmatched += 1
            continue
        PlaceFeature.objects.update_or_create(
            place=place,
            defaults={"style_vector": row["style_vector"], "content_vector": row["content_vector"]},
        )
        matched += 1
    return LoadSummary(matched=matched, unmatched=unmatched)
