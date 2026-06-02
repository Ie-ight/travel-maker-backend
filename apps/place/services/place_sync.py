"""Tour API 소량 수집 오케스트레이션 (단계 2).

areaBasedList2 → detailCommon2 → detailImage2 파이프라인으로 Place·PlaceImage를 적재한다.
값 정규화(§3-4,5)·필드 매핑(§4)·수집 정책(§7)을 여기서 처리한다.
대량 적재·재시도·로깅은 단계 6 범위.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.place.models import Place, PlaceImage, PlaceInfo
from apps.place.services.place_info_mapping import (
    BOOLEAN_FIELDS,
    LODGING_CHECKIN_KEY,
    LODGING_CHECKOUT_KEY,
    LODGING_TYPE_ID,
    PLACE_INFO_FIELD_MAP,
)
from apps.place.services.tagging import assign_deterministic_tags
from apps.place.services.tour_api import TourApiClient, TourApiError

_HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)


def _blank_to_none(value: Any) -> str | None:
    """빈 문자열 ""을 None으로 정규화한다(§3-5). 그 외는 strip한 문자열."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_decimal(value: Any) -> Decimal | None:
    """좌표 등 숫자 문자열을 Decimal로 변환한다(§3-4). 빈 값/파싱 실패는 None."""
    text = _blank_to_none(value)
    if text is None:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _clean_homepage(value: Any) -> str | None:
    """homepage 원문(`<a href=...>`)에서 URL만 추출한다. 앵커가 없으면 원문 유지."""
    text = _blank_to_none(value)
    if text is None:
        return None
    match = _HREF_RE.search(text)
    return match.group(1) if match else text


def _to_bool(value: Any) -> bool | None:
    """편의성 boolean 정규화(§4). 음성 지표("불가"/"없음") 포함 시 False, 다른 값 있으면 True, 빈 값이면 None.

    실데이터에 "불가"(예: "불가능") 외에 "없음"(예: "유모차 없음")도 '불가'를 뜻해 함께 False 처리한다.
    """
    text = _blank_to_none(value)
    if text is None:
        return None
    return "불가" not in text and "없음" not in text


def _lodging_operating_hours(intro_item: dict[str, Any]) -> str | None:
    """숙박(32)은 운영시간이 checkin/checkout으로 분리돼 와서 하나로 합친다."""
    checkin = _blank_to_none(intro_item.get(LODGING_CHECKIN_KEY))
    checkout = _blank_to_none(intro_item.get(LODGING_CHECKOUT_KEY))
    parts = []
    if checkin:
        parts.append(f"체크인 {checkin}")
    if checkout:
        parts.append(f"체크아웃 {checkout}")
    return " / ".join(parts) or None


def build_place_info_defaults(content_type_id: int, intro_item: dict[str, Any]) -> dict[str, Any] | None:
    """detailIntro2 항목을 PlaceInfo 필드로 매핑한다(타입별, §4).

    매핑이 없는 타입(축제·여행코스 등)은 None을 반환한다.
    """
    field_map = PLACE_INFO_FIELD_MAP.get(content_type_id)
    if field_map is None:
        return None
    defaults: dict[str, Any] = {}
    for model_field, api_key in field_map.items():
        raw = intro_item.get(api_key)
        defaults[model_field] = _to_bool(raw) if model_field in BOOLEAN_FIELDS else _blank_to_none(raw)
    if content_type_id == LODGING_TYPE_ID:  # 운영시간 = 체크인/체크아웃 조합
        defaults["operating_hours"] = _lodging_operating_hours(intro_item)
    return defaults


def build_place_defaults(list_item: dict[str, Any], common_item: dict[str, Any] | None) -> dict[str, Any]:
    """areaBasedList2 항목 + detailCommon2 항목을 Place 필드로 매핑한다(§4)."""
    common = common_item or {}
    return {
        "place_name": _blank_to_none(list_item.get("title")) or "",
        "content_type_id": int(list_item["contenttypeid"]),
        "latitude": _to_decimal(list_item.get("mapy")),
        "longitude": _to_decimal(list_item.get("mapx")),
        "address_primary": _blank_to_none(list_item.get("addr1")),
        "address_detail": _blank_to_none(list_item.get("addr2")),
        "tel": _blank_to_none(list_item.get("tel")),
        "zipcode": _blank_to_none(list_item.get("zipcode")),
        "lcls_systm1": _blank_to_none(list_item.get("lclsSystm1")),
        "lcls_systm2": _blank_to_none(list_item.get("lclsSystm2")),
        "lcls_systm3": _blank_to_none(list_item.get("lclsSystm3")),
        "description": _blank_to_none(common.get("overview")),
        "homepage": _clean_homepage(common.get("homepage")),
    }


def save_images(
    place: Place,
    image_items: list[dict[str, Any]],
    *,
    firstimage: str | None,
    firstimage2: Any = None,
) -> int:
    """이미지 저장 정책(§4) 적용. 저장한 이미지 행 수를 반환한다.

    detailImage2 결과가 있으면 그것을, 없으면 firstimage/firstimage2를 대표 이미지로 저장한다.
    """
    rows: list[tuple[str, str | None]] = []
    if image_items:
        for item in image_items:
            origin = _blank_to_none(item.get("originimgurl"))
            small = _blank_to_none(item.get("smallimageurl"))
            image_url = origin or small
            if image_url is None:  # 둘 다 빈 값이면 저장하지 않음(§4-3)
                continue
            rows.append((image_url, small))
    elif firstimage:
        rows.append((firstimage, _blank_to_none(firstimage2)))

    for order, (image_url, thumbnail_url) in enumerate(rows):
        PlaceImage.objects.update_or_create(
            place=place,
            image_url=image_url,
            defaults={"thumbnail_url": thumbnail_url, "is_main": order == 0, "order": order},
        )
    return len(rows)


@dataclass
class SyncSummary:
    fetched: int = 0
    skipped_no_image: int = 0
    created: int = 0
    updated: int = 0
    images_saved: int = 0
    info_saved: int = 0


def sync_area(
    content_type_id: int,
    *,
    ldong_regn_cd: str | None = None,
    num_of_rows: int = 10,
    pages: int = 1,
    dry_run: bool = False,
    client: TourApiClient | None = None,
) -> SyncSummary:
    """한 타입·(선택)한 지역으로 소량 수집한다.

    dry_run이면 목록만 조회하고 상세 호출·DB 저장은 하지 않는다(수집 대상 미리보기).
    """
    api = client or TourApiClient()
    summary = SyncSummary()

    for page in range(1, pages + 1):
        list_items = api.area_based_list(
            content_type_id,
            ldong_regn_cd=ldong_regn_cd,
            num_of_rows=num_of_rows,
            page_no=page,
        )
        if not list_items:
            break

        for list_item in list_items:
            summary.fetched += 1
            firstimage = _blank_to_none(list_item.get("firstimage"))
            if firstimage is None:  # firstimage 없으면 저장·detailImage 호출 안 함(§7-2)
                summary.skipped_no_image += 1
                continue
            if dry_run:
                continue

            content_id = int(list_item["contentid"])
            common = _safe_detail_common(api, content_id)
            place, created = Place.objects.update_or_create(
                content_id=content_id,
                defaults=build_place_defaults(list_item, common),
            )
            if created:
                summary.created += 1
            else:
                summary.updated += 1

            images = _safe_detail_image(api, content_id)
            summary.images_saved += save_images(
                place,
                images,
                firstimage=firstimage,
                firstimage2=list_item.get("firstimage2"),
            )

            # 운영 정보(PlaceInfo)는 매핑이 있는 타입만 detailIntro2 호출(불필요 호출 회피, §3)
            if content_type_id in PLACE_INFO_FIELD_MAP:
                intro = _safe_detail_intro(api, content_id, content_type_id)
                if intro is not None:
                    PlaceInfo.objects.update_or_create(
                        place=place,
                        defaults=build_place_info_defaults(content_type_id, intro),
                    )
                    summary.info_saved += 1

            # 결정론 태그(지역·편의성) 부여 — PlaceInfo 저장 이후 (§8, 4단계)
            assign_deterministic_tags(place)

    return summary


def _safe_detail_common(api: TourApiClient, content_id: int) -> dict[str, Any] | None:
    """detailCommon2는 보강용이라 실패해도 Place 저장을 막지 않는다."""
    try:
        return api.detail_common(content_id)
    except TourApiError:
        return None


def _safe_detail_image(api: TourApiClient, content_id: int) -> list[dict[str, Any]]:
    """detailImage2 실패 시 빈 리스트 → firstimage 폴백."""
    try:
        return api.detail_image(content_id)
    except TourApiError:
        return []


def _safe_detail_intro(api: TourApiClient, content_id: int, content_type_id: int) -> dict[str, Any] | None:
    """detailIntro2는 보강용이라 실패해도 Place 저장을 막지 않는다."""
    try:
        return api.detail_intro(content_id, content_type_id)
    except TourApiError:
        return None
