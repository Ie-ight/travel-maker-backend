"""결정론 태깅 (단계 4, §8): `지역`(주소 파싱) + `편의성`(PlaceInfo boolean).

AI 판단이 필요한 `여행 스타일`·`세부 테마`·`동행`은 5단계에서 부여한다.
태그가 시드(`seed_tags`)돼 있어야 부여되며, 안 돼 있으면 조용히 skip한다.
"""

from apps.place.models import Place, PlaceInfo, Tag
from apps.place.services.tag_seeds import (
    AI_TAG_TYPES,
    FACILITY_BOOL_TAGS,
    FACILITY_TAG_TYPE,
    FREE_ADMISSION_TAG,
    REGION_PREFIX_MAP,
    REGION_TAG_TYPE,
)

#: assign_deterministic_tags가 재계산(제거 후 재부여)하는 tag_type. AI 태그는 건드리지 않는다.
DETERMINISTIC_TAG_TYPES = (REGION_TAG_TYPE, FACILITY_TAG_TYPE)


def _region_tag_name(address_primary: str | None) -> str | None:
    """addr1 첫 토큰(시·도)을 `지역` tag_name으로 변환한다(매칭 없으면 None)."""
    if not address_primary:
        return None
    tokens = address_primary.split()
    if not tokens:
        return None
    return REGION_PREFIX_MAP.get(tokens[0])


def _facility_tag_names(place: Place) -> list[str]:
    """PlaceInfo boolean이 True인 편의성 + 무료입장(admission_fee에 "무료")을 tag_name 목록으로."""
    try:
        info = place.info
    except PlaceInfo.DoesNotExist:
        return []
    names = [tag for field, tag in FACILITY_BOOL_TAGS.items() if getattr(info, field) is True]
    if info.admission_fee and "무료" in info.admission_fee:
        names.append(FREE_ADMISSION_TAG)
    return names


def assign_region_tag(place: Place) -> str | None:
    """addr1 기반 `지역` 태그를 부여하고 부여한 tag_name을 반환한다(없으면 None)."""
    name = _region_tag_name(place.address_primary)
    if name is None:
        return None
    tag = Tag.objects.filter(tag_name=name, tag_type=REGION_TAG_TYPE).first()
    if tag is None:  # 시드 안 됨
        return None
    place.tags.add(tag)
    return name


def assign_facility_tags(place: Place) -> list[str]:
    """PlaceInfo 기반 `편의성` 태그를 부여하고 부여한 tag_name 목록을 반환한다."""
    names = _facility_tag_names(place)
    if not names:
        return []
    tags = list(Tag.objects.filter(tag_name__in=names, tag_type=FACILITY_TAG_TYPE))
    if tags:
        place.tags.add(*tags)
    return [tag.tag_name for tag in tags]


def assign_deterministic_tags(place: Place) -> None:
    """`지역`·`편의성` 태그를 멱등 재부여한다(기존 결정론 태그 제거 후 재계산).

    재실행·PlaceInfo 변경에도 일관되며, AI tag_type(여행 스타일 등)은 보존한다.
    """
    existing = list(place.tags.filter(tag_type__in=DETERMINISTIC_TAG_TYPES))
    if existing:
        place.tags.remove(*existing)
    assign_region_tag(place)
    assign_facility_tags(place)


def assign_ai_tags(place: Place, names: list[str]) -> list[str]:
    """AI 태그(여행 스타일·세부 테마·동행)를 멱등 재부여한다(기존 AI 태그 제거 후 재계산).

    결정론 태그(지역·편의성)는 보존한다. 시드된 태그만 부여하며 부여한 tag_name을 반환한다.
    """
    existing = list(place.tags.filter(tag_type__in=AI_TAG_TYPES))
    if existing:
        place.tags.remove(*existing)
    if not names:
        return []
    tags = list(Tag.objects.filter(tag_name__in=names, tag_type__in=AI_TAG_TYPES))
    if tags:
        place.tags.add(*tags)
    return [tag.tag_name for tag in tags]
