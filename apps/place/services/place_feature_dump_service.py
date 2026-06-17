"""PlaceFeature 덤프/적재 — 환경(로컬 ↔ 배포) 간 이전용.

place_id(PK)는 환경마다 다를 수 있으므로 Tour API 고유값인 Place.content_id를
매칭 키로 사용한다.
"""

import itertools
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


def serialize_place_features(queryset: Iterable[PlaceFeature]) -> Iterable[PlaceFeatureRow]:
    """PlaceFeature 쿼리셋을 content_id 기준 JSON 직렬화 가능한 행 목록으로 변환한다(Generator)."""
    for feature in queryset:
        yield {
            "content_id": feature.place.content_id,
            "style_vector": _round_vector(feature.style_vector) if feature.style_vector is not None else None,
            "content_vector": _round_vector(feature.content_vector) if feature.content_vector is not None else None,
        }


def load_place_features(rows: Iterable[PlaceFeatureRow]) -> LoadSummary:
    """content_id로 Place를 찾아 PlaceFeature를 1000개 단위로 bulk_create(upsert)한다. content_id 미존재 시 건너뜀."""
    matched = unmatched = 0

    # 1000개씩 청크 단위로 처리 (Python 3.12+ 내장 batched 사용)
    for batch_rows in itertools.batched(rows, 1000):
        content_ids = [r["content_id"] for r in batch_rows]

        # 1. 쿼리 최적화: 현재 배치에 해당하는 Place ID를 한 번에 조회
        place_mapping = dict(Place.objects.filter(content_id__in=content_ids).values_list("content_id", "id"))

        features_to_create = []
        for row in batch_rows:
            place_id = place_mapping.get(row["content_id"])
            if place_id is None:
                unmatched += 1
                continue

            features_to_create.append(
                PlaceFeature(
                    place_id=place_id,
                    style_vector=row["style_vector"],
                    content_vector=row["content_vector"],
                )
            )
            matched += 1

        # 2. Bulk Insert or Update
        if features_to_create:
            PlaceFeature.objects.bulk_create(
                features_to_create,
                update_conflicts=True,
                unique_fields=["place_id"],  # PK 기준으로 충돌 감지
                update_fields=["style_vector", "content_vector"],
            )

    return LoadSummary(matched=matched, unmatched=unmatched)
