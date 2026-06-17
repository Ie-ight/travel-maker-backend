"""Tour API 수집 오케스트레이션 (단계 2 소량 + 단계 6 대량).

areaBasedList2 → detailCommon2 → detailImage2 (+ detailIntro2)로 Place·PlaceImage·PlaceInfo를 적재한다.
값 정규화(§3-4,5)·필드 매핑(§4)·수집 정책(§7)을 여기서 처리한다.
- sync_area: 한 타입·소량(단계 2 검증).
- sync_all: 전체 타입 전국 페이지네이션 대량 적재 + 로깅·재개(단계 6). 재시도/백오프는 TourApiClient가 담당.
"""

import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import DatabaseError, transaction
from django.db.models import Q

from apps.place.models import Place, PlaceImage, PlaceInfo
from apps.place.services.place_info_mapping import (
    BOOLEAN_FIELDS,
    INFOCENTER_KEY,
    LODGING_CHECKIN_KEY,
    LODGING_CHECKOUT_KEY,
    LODGING_TYPE_ID,
    PLACE_INFO_FIELD_MAP,
)
from apps.place.services.tagging import assign_deterministic_tags
from apps.place.services.tour_api import AllKeysExhaustedError, TourApiClient, TourApiError

logger = logging.getLogger("place.sync")

#: 대량 적재 대상 타입(§2). 25 여행코스(COURSE)는 PlaceInfo 스키마와 안 맞고 사용 안 해 제외.
_CT = Place.ContentType
DEFAULT_CONTENT_TYPE_IDS: tuple[int, ...] = (
    _CT.TOURIST,
    _CT.CULTURE,
    _CT.FESTIVAL,
    _CT.LEPORTS,
    _CT.LODGING,
    _CT.SHOPPING,
    _CT.FOOD,
)

_HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")
_HANGUL_TRAIL_RE = re.compile(r"[가-힣]+$")
# infocenter* 첫 전화번호 패턴: 하이픈형(하이픈 주변 공백 오타 허용) / 특수번호(DDDD-DDDD) / 하이픈
# 없는 번호(0으로 시작 9~12자리 — 날짜·ID 오인 방지). 앞이 숫자면(중간) 시작 안 함. 라벨·이메일·복수번호·
# 내선(~N)·축약 둘째번호 등 첫 완전 번호 뒤의 부가 텍스트는 모두 제외된다(첫 대표번호 1개만 남긴다).
_PHONE_RE = re.compile(r"(?<!\d)(?:\d{2,4} *- *\d{3,4} *- *\d{4}|\d{4} *- *\d{4}|0\d{8,11})")
#: 4자리 국번 접두(안심·평생번호 등) — bare 번호 하이픈 삽입 시 국번 길이 판정용
_TEL_AREA4_PREFIXES = frozenset({"0303", "0502", "0503", "0504", "0505", "0506", "0507", "0508"})

# PlaceInfo 자유 텍스트(operating_hours 등) 정제용. detailIntro2 텍스트엔 줄바꿈 의도의 <br> 계열(<br>,
# <br/>, <br />, <br >, <vr> 오타, 닫는 > 대신 <를 친 <br< 같은 깨진 변형)과 드물게 <a> 앵커가 섞여
# 온다(실측: 그 외 태그·HTML 엔티티 없음). br/vr 뒤가 공백·/·<·>·끝일 때만 잡아 단어(<brunch> 등) 오매칭을 막는다.
_BR_RE = re.compile(r"<\s*/?\s*(?:br|vr)(?=[\s/<>]|$)\s*/?\s*[<>]?", re.IGNORECASE)  # 줄바꿈 태그 → \n
_TAG_RE = re.compile(r"<[^>]+>")  # 그 외 태그(<a> 등) 제거 — 내부 텍스트는 유지
_WS_LINE_RE = re.compile(r"[ \t]*\n[ \t\n]*")  # 줄바꿈 주변 공백·중복 줄바꿈 collapse(<br>\n → \n)
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")  # 줄 안 다중 공백 정리


def _blank_to_none(value: Any) -> str | None:
    """빈 문자열 ""을 None으로 정규화한다(§3-5). 그 외는 strip한 문자열."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_info_text(value: Any) -> str | None:
    """PlaceInfo 자유 텍스트의 HTML 마크업을 제거하고 멀티라인 평문으로 정규화한다.

    detailIntro2의 운영시간·휴무일·입장료 등은 줄바꿈 의도의 <br> 계열과 드문 <a> 앵커가 섞여 온다.
    응답 계약은 그대로 str로 두되 값만 정리한다: <br>는 \\n으로, 그 외 태그는 제거(내부 텍스트 유지),
    <br>\\n처럼 실제 줄바꿈과 겹쳐 생기는 중복 줄바꿈·줄 앞뒤 공백은 collapse한다. 프론트는 split("\\n")만
    하면 된다. 빈 값은 None.
    """
    text = _blank_to_none(value)
    if text is None:
        return None
    text = _BR_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = _WS_LINE_RE.sub("\n", text)
    text = _MULTISPACE_RE.sub(" ", text)
    return text.strip() or None


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
    """homepage 원문에서 첫 번째 URL만 추출한다. href 앵커 → 평문 URL 순으로 시도."""
    text = _blank_to_none(value)
    if text is None:
        return None
    match = _HREF_RE.search(text)
    if match:
        return match.group(1)
    match = _URL_RE.search(text)
    if match:
        return _HANGUL_TRAIL_RE.sub("", match.group(0)) or None
    return None


def _hyphenate_bare(digits: str) -> str:
    """하이픈 없는 전화번호 숫자열(0으로 시작)에 한국 표기 규칙으로 하이픈을 넣는다(국번-중간-끝4).

    국번 길이: 02(서울)=2, 안심·평생번호(0507 등)=4, 그 외(0XX·010·070)=3. 규칙으로 세 토막을 못
    만드는 비정형(중간 토막 없음)은 원형을 유지한다.
    """
    if digits.startswith("02"):
        area_len = 2
    elif digits[:4] in _TEL_AREA4_PREFIXES:
        area_len = 4
    else:
        area_len = 3
    area, body = digits[:area_len], digits[area_len:]
    if len(body) <= 4:  # 중간 토막이 안 나오는 비정형 → 원형 유지
        return digits
    return f"{area}-{body[:-4]}-{body[-4:]}"


def _clean_tel(value: Any) -> str | None:
    """전화번호 원문에서 첫 전화번호만 추출·정규화한다(번호 없으면 None).

    infocenter*는 '062-365-8733'처럼 번호만 오기도 하지만 '○○관광안내소 062-...'처럼 라벨을 달거나,
    '033-..., email@x', '010-... / 010-...', '031-770-1072~5', '031-770-1072, 1079'처럼 부가 정보·
    내선·복수 번호가 붙어 오기도 한다. 첫 완전 번호 1개만 뽑아 라벨·이메일·내선(~N)·둘째 번호 등은 모두
    버린다. 하이픈 주변 공백 오타('02-360- 4351')는 제거하고, 하이픈 없는 번호('0614718500')는 한국
    표기로 하이픈을 넣는다. 번호가 없으면(순수 텍스트) None을 반환한다.
    """
    text = _blank_to_none(value)
    if text is None:
        return None
    match = _PHONE_RE.search(text)
    if match is None:
        return None
    token = match.group(0).replace(" ", "")  # 하이픈 주변 공백 오타 보정
    return token if "-" in token else _hyphenate_bare(token)


def _resolve_tel(content_type_id: int, list_item: dict[str, Any], intro_item: dict[str, Any] | None) -> str | None:
    """전화번호를 결정한다: detailIntro2 infocenter*(타입별)를 우선, 없으면 목록 tel.

    목록(areaBasedList2) tel은 축제 외 타입에서 거의 비어 오고(실측 0%), 실제 번호는 detailIntro2
    infocenter*에 온다(실측 ~91%). 축제 등 detailIntro2를 호출하지 않는 타입은 목록 tel을 그대로 쓴다.
    """
    if intro_item is not None:
        key = INFOCENTER_KEY.get(content_type_id)
        if key is not None:
            tel = _clean_tel(intro_item.get(key))
            if tel is not None:
                return tel
    return _clean_tel(list_item.get("tel"))


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
        # boolean은 가능/불가 정규화, 그 외 자유 텍스트는 HTML(<br> 등) 제거·줄바꿈 정규화
        defaults[model_field] = _to_bool(raw) if model_field in BOOLEAN_FIELDS else _clean_info_text(raw)
    if content_type_id == LODGING_TYPE_ID:  # 운영시간 = 체크인/체크아웃 조합
        defaults["operating_hours"] = _lodging_operating_hours(intro_item)
    return defaults


def build_place_defaults(
    list_item: dict[str, Any],
    common_item: dict[str, Any] | None,
    intro_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """areaBasedList2 + detailCommon2(+detailIntro2) 항목을 Place 필드로 매핑한다(§4).

    tel은 목록에 거의 비어 와서 detailIntro2 infocenter*(타입별)를 우선 사용한다(_resolve_tel).
    """
    common = common_item or {}
    content_type_id = int(list_item["contenttypeid"])
    return {
        "place_name": _blank_to_none(list_item.get("title")) or "",
        "content_type_id": content_type_id,
        "latitude": _to_decimal(list_item.get("mapy")),
        "longitude": _to_decimal(list_item.get("mapx")),
        "address_primary": _blank_to_none(list_item.get("addr1")),
        "address_detail": _blank_to_none(list_item.get("addr2")),
        "tel": _resolve_tel(content_type_id, list_item, intro_item),
        "zipcode": _blank_to_none(list_item.get("zipcode")),
        "lcls_systm1": _blank_to_none(list_item.get("lclsSystm1")),
        "lcls_systm2": _blank_to_none(list_item.get("lclsSystm2")),
        "lcls_systm3": _blank_to_none(list_item.get("lclsSystm3")),
        "description": _blank_to_none(common.get("overview")),
        "homepage": _clean_homepage(common.get("homepage")),
        "source_modified_at": _blank_to_none(list_item.get("modifiedtime")),  # 증분 비교 기준(단계 7)
        "is_active": True,  # 수집/갱신되는 곳은 활성(소프트삭제 복구 포함)
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
    skipped_existing: int = 0
    created: int = 0
    updated: int = 0
    images_saved: int = 0
    info_saved: int = 0
    deactivated: int = 0  # 소프트삭제(showflag=0, 단계 7)
    skipped_unchanged: int = 0  # modifiedtime 미변경 스킵(단계 7)
    skipped_detail_failed: int = 0  # 상세 호출 실패로 저장 건너뜀(429 등) → 다음 run에서 재시도
    skipped_save_failed: int = 0  # DB 저장 실패로 건너뜀(데이터 형식 등) → 한 레코드 때문에 전체 중단 방지

    def add(self, other: "SyncSummary") -> None:
        """다른 요약을 누적한다(타입별 → 전체 합산)."""
        for field in fields(self):
            setattr(self, field.name, getattr(self, field.name) + getattr(other, field.name))


def sync_area(
    content_type_id: int,
    *,
    ldong_regn_cd: str | None = None,
    num_of_rows: int = 10,
    pages: int = 1,
    dry_run: bool = False,
    arrange: str | None = None,
    client: TourApiClient | None = None,
) -> SyncSummary:
    """한 타입·(선택)한 지역으로 소량 수집한다(단계 2 검증).

    arrange로 정렬을 지정할 수 있다(C=수정일순 등). dry_run이면 목록만 조회하고 저장은 하지 않는다.
    """
    api = client or TourApiClient()
    summary = SyncSummary()
    for page in range(1, pages + 1):
        list_items = api.area_based_list(
            content_type_id, ldong_regn_cd=ldong_regn_cd, num_of_rows=num_of_rows, page_no=page, arrange=arrange
        )
        if not list_items:
            break
        for list_item in list_items:
            _process_list_item(api, content_type_id, list_item, dry_run=dry_run, summary=summary)
        time.sleep(0.1)
    return summary


def sync_all(
    content_type_ids: Sequence[int] = DEFAULT_CONTENT_TYPE_IDS,
    *,
    num_of_rows: int = 50,
    max_pages: int | None = None,
    skip_existing: bool = False,
    dry_run: bool = False,
    arrange: str | None = None,
    client: TourApiClient | None = None,
) -> SyncSummary:
    """전체 타입을 전국 페이지네이션으로 대량 적재한다(단계 6).

    각 타입을 빈 페이지/마지막 페이지까지 순회한다(max_pages로 상한). arrange로 정렬을 지정할 수 있다
    (C=수정일순 → 최근 수정분 우선). 목록 호출이 끝내 실패하면 그 타입만 중단하고 다음 타입으로 넘어간다
    (전체 abort 방지). skip_existing이면 이미 저장된 content_id의 상세 호출·저장을 건너뛴다(재개·증분 비용 절감).
    """
    api = client or TourApiClient()
    total = SyncSummary()
    for content_type_id in content_type_ids:
        existing_ids: set[int] | None = None
        if skip_existing:
            existing_ids = set(
                Place.objects.filter(content_type_id=content_type_id).values_list("content_id", flat=True)
            )
        sub = SyncSummary()
        logger.info(
            "타입 %s 수집 시작 (skip_existing=%s, 기존 %s건)",
            content_type_id,
            skip_existing,
            len(existing_ids) if existing_ids is not None else "-",
        )
        page = 1
        while max_pages is None or page <= max_pages:
            list_items = _safe_area_based_list(
                api, content_type_id, num_of_rows=num_of_rows, page_no=page, arrange=arrange
            )
            if not list_items:
                break
            for list_item in list_items:
                _process_list_item(
                    api,
                    content_type_id,
                    list_item,
                    dry_run=dry_run,
                    summary=sub,
                    skip_existing=skip_existing,
                    existing_ids=existing_ids,
                )
            logger.info("타입 %s page %d 처리 (%d건)", content_type_id, page, len(list_items))
            time.sleep(0.1)
            if len(list_items) < num_of_rows:  # 마지막 페이지
                break
            page += 1
        logger.info(
            "타입 %s 완료: 생성 %d·갱신 %d·이미지없음 %d·기존스킵 %d·상세실패스킵 %d·저장실패스킵 %d",
            content_type_id,
            sub.created,
            sub.updated,
            sub.skipped_no_image,
            sub.skipped_existing,
            sub.skipped_detail_failed,
            sub.skipped_save_failed,
        )
        total.add(sub)
    logger.info(
        "전체 수집 완료: 조회 %d·생성 %d·갱신 %d·이미지 %d·운영정보 %d·이미지없음 %d·기존스킵 %d·상세실패스킵 %d·저장실패스킵 %d",
        total.fetched,
        total.created,
        total.updated,
        total.images_saved,
        total.info_saved,
        total.skipped_no_image,
        total.skipped_existing,
        total.skipped_detail_failed,
        total.skipped_save_failed,
    )
    return total


def _process_list_item(
    api: TourApiClient,
    content_type_id: int,
    list_item: dict[str, Any],
    *,
    dry_run: bool,
    summary: SyncSummary,
    skip_existing: bool = False,
    existing_ids: set[int] | None = None,
) -> None:
    """목록 항목 1건 처리: firstimage 필터 → Place·이미지·PlaceInfo·결정론 태그(§4,§7,§8).

    sync_area·sync_all 공용. skip_existing이면 이미 저장된 content_id의 상세 호출·저장을 건너뛴다.
    """
    summary.fetched += 1
    firstimage = _blank_to_none(list_item.get("firstimage"))
    if firstimage is None:  # firstimage 없으면 저장·detailImage 호출 안 함(§7-2)
        summary.skipped_no_image += 1
        return

    content_id = int(list_item["contentid"])
    if skip_existing and existing_ids is not None and content_id in existing_ids:
        summary.skipped_existing += 1
        return
    if dry_run:
        return

    # 상세 보강을 먼저 모두 조회한다. 하나라도 호출 실패(429·타임아웃 등)면 이 장소를 저장하지 않고
    # 건너뛴다 → degraded 레코드(설명·이미지 누락) 방지. 다음 run에서 skip_existing이 전체 재시도한다.
    # 운영 정보(PlaceInfo)는 매핑이 있는 타입만 detailIntro2 호출(불필요 호출 회피, §3).
    try:
        common = api.detail_common(content_id)
        images = api.detail_image(content_id)
        intro = api.detail_intro(content_id, content_type_id) if content_type_id in PLACE_INFO_FIELD_MAP else None
    except AllKeysExhaustedError:
        raise  # 모든 키 소진은 전역 치명 → 레코드 스킵이 아니라 run 전체 중단
    except TourApiError as exc:
        logger.warning("상세 호출 실패로 건너뜀(다음 수집에서 재시도) content_id=%s: %s", content_id, exc)
        summary.skipped_detail_failed += 1
        return

    # 한 레코드의 DB 오류(데이터 형식 등)가 전체 run을 중단시키지 않도록 트랜잭션으로 묶고,
    # 실패 시 통째로 롤백·스킵한다(부분 저장 방지). 다음 run에서 skip_existing이 재시도.
    try:
        with transaction.atomic():
            place, created = Place.objects.update_or_create(
                content_id=content_id, defaults=build_place_defaults(list_item, common, intro)
            )
            images_saved = save_images(place, images, firstimage=firstimage, firstimage2=list_item.get("firstimage2"))
            info_saved = 0
            if intro is not None:
                PlaceInfo.objects.update_or_create(
                    place=place, defaults=build_place_info_defaults(content_type_id, intro)
                )
                info_saved = 1
            # 결정론 태그(지역·편의성) 부여 — PlaceInfo 저장 이후 (§8, 4단계)
            assign_deterministic_tags(place)
    except DatabaseError as exc:
        logger.warning("DB 저장 실패로 건너뜀(데이터 형식 등) content_id=%s: %s", content_id, exc)
        summary.skipped_save_failed += 1
        return

    if created:
        summary.created += 1
    else:
        summary.updated += 1
    summary.images_saved += images_saved
    summary.info_saved += info_saved


def _safe_area_based_list(
    api: TourApiClient, content_type_id: int, *, num_of_rows: int, page_no: int, arrange: str | None = None
) -> list[dict[str, Any]]:
    """목록 호출 실패(재시도 소진 포함) 시 로그 후 빈 리스트 → 해당 타입 종료(전체 abort 방지).

    단, 모든 키 소진(AllKeysExhaustedError)은 다음 타입에서도 100% 실패하는 전역 치명 조건이라
    삼키지 않고 전파해 run 전체를 중단한다.
    """
    try:
        return api.area_based_list(content_type_id, num_of_rows=num_of_rows, page_no=page_no, arrange=arrange)
    except AllKeysExhaustedError:
        raise
    except TourApiError as exc:
        logger.error("타입 %s page %d 목록 호출 실패, 이 타입 중단: %s", content_type_id, page_no, exc)
        return []


def sync_incremental(
    content_type_ids: Sequence[int] = DEFAULT_CONTENT_TYPE_IDS,
    *,
    num_of_rows: int = 50,
    max_pages: int | None = None,
    dry_run: bool = False,
    client: TourApiClient | None = None,
) -> SyncSummary:
    """areaBasedSyncList2로 변경분만 반영한다(단계 7).

    목록 modifiedtime을 저장된 source_modified_at과 비교해 신규·변경만 detail을 재조회하고(미변경은 0콜),
    showflag=0은 소프트삭제(is_active=False)한다. 단계 6의 _process_list_item/재시도를 재사용.
    """
    api = client or TourApiClient()
    total = SyncSummary()
    for content_type_id in content_type_ids:
        # 기존 {content_id: source_modified_at} — 변경 판정 기준
        existing: dict[int, str | None] = dict(
            Place.objects.filter(content_type_id=content_type_id).values_list("content_id", "source_modified_at")
        )
        sub = SyncSummary()
        logger.info("타입 %s 증분 시작 (기존 %d건)", content_type_id, len(existing))
        page = 1
        while max_pages is None or page <= max_pages:
            list_items = _safe_area_based_sync_list(api, content_type_id, num_of_rows=num_of_rows, page_no=page)
            if not list_items:
                break
            for list_item in list_items:
                _process_sync_item(api, content_type_id, list_item, existing, dry_run=dry_run, summary=sub)
            logger.info("타입 %s page %d 처리 (%d건)", content_type_id, page, len(list_items))
            time.sleep(0.1)
            if len(list_items) < num_of_rows:  # 마지막 페이지
                break
            page += 1
        logger.info(
            "타입 %s 완료: 생성 %d·갱신 %d·미변경 %d·삭제 %d",
            content_type_id,
            sub.created,
            sub.updated,
            sub.skipped_unchanged,
            sub.deactivated,
        )
        total.add(sub)
    logger.info(
        "전체 증분 완료: 생성 %d·갱신 %d·미변경 %d·삭제 %d·이미지없음 %d",
        total.created,
        total.updated,
        total.skipped_unchanged,
        total.deactivated,
        total.skipped_no_image,
    )
    return total


def _process_sync_item(
    api: TourApiClient,
    content_type_id: int,
    list_item: dict[str, Any],
    existing: dict[int, str | None],
    *,
    dry_run: bool,
    summary: SyncSummary,
) -> None:
    """증분 항목 1건: showflag=0 소프트삭제 / 신규·변경 수집 / 미변경 스킵."""
    content_id = int(list_item["contentid"])
    if _blank_to_none(list_item.get("showflag")) == "0":  # 비공개/삭제
        if content_id in existing:
            if not dry_run:
                Place.objects.filter(content_id=content_id).update(is_active=False)
            summary.deactivated += 1
        return

    if content_id not in existing:  # 신규
        _process_list_item(api, content_type_id, list_item, dry_run=dry_run, summary=summary)
        return

    # 기존: modifiedtime 비교(고정폭 문자열). 저장값 없거나 더 크면 변경 → 재수집(update_or_create로 갱신)
    new_mtime = _blank_to_none(list_item.get("modifiedtime"))
    stored = existing[content_id]
    if new_mtime is not None and (stored is None or new_mtime > stored):
        _process_list_item(api, content_type_id, list_item, dry_run=dry_run, summary=summary)
    else:
        summary.skipped_unchanged += 1


def _safe_area_based_sync_list(
    api: TourApiClient, content_type_id: int, *, num_of_rows: int, page_no: int
) -> list[dict[str, Any]]:
    """증분 목록 호출 실패 시 로그 후 빈 리스트 → 해당 타입 종료(전체 abort 방지).

    모든 키 소진(AllKeysExhaustedError)만은 전파해 run 전체를 중단한다.
    """
    try:
        return api.area_based_sync_list(content_type_id, num_of_rows=num_of_rows, page_no=page_no)
    except AllKeysExhaustedError:
        raise
    except TourApiError as exc:
        logger.error("타입 %s page %d 증분 목록 호출 실패, 이 타입 중단: %s", content_type_id, page_no, exc)
        return []


@dataclass
class DetailBackfillSummary:
    """detailIntro2 백필 결과 요약(tel + PlaceInfo)."""

    target: int = 0  # 대상(빈 tel) 장소 수
    processed: int = 0  # detailIntro2 호출 성공
    tel_updated: int = 0  # tel 채운 건수
    tel_missing: int = 0  # infocenter*가 비어 tel을 못 채움
    info_created: int = 0  # PlaceInfo 신규 생성
    info_refreshed: int = 0  # 기존 PlaceInfo 갱신(refresh_info=True일 때만)
    errors: int = 0  # 호출 실패(다음 실행에서 재시도)
    aborted: bool = False  # 모든 API 키 한도 소진으로 중단됨


def backfill_details(
    *,
    content_type_id: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    refresh_info: bool = False,
    client: TourApiClient | None = None,
) -> DetailBackfillSummary:
    """tel이 빈 기존 장소를 detailIntro2로 백필한다(tel + 누락 PlaceInfo, 멱등·재개, 신규 수집 없음).

    detailIntro2를 한 번 호출해 (1) infocenter*로 tel을 채우고 (2) PlaceInfo가 없으면 생성한다.
    refresh_info=True면 기존 PlaceInfo도 새 intro로 갱신한다(기본 False — 누락분만 생성).
    축제 등 detailIntro2를 호출하지 않는 타입(INFOCENTER_KEY 없음)은 제외한다. tel이 채워지면 다음
    실행 대상에서 자동으로 빠지므로, 키 한도로 중단(aborted)돼도 다시 실행하면 남은 건부터 이어간다.
    """
    api = client or TourApiClient()
    summary = DetailBackfillSummary()

    queryset = Place.objects.filter(content_type_id__in=INFOCENTER_KEY).filter(Q(tel__isnull=True) | Q(tel=""))
    if content_type_id is not None:
        queryset = queryset.filter(content_type_id=content_type_id)
    queryset = queryset.order_by("id")
    if limit is not None:
        queryset = queryset[:limit]
    # 호출 중 갱신하므로 대상을 먼저 확정한다(쓰기와 커서 동시 진행 회피).
    targets = list(queryset.values_list("id", "content_id", "content_type_id"))
    summary.target = len(targets)
    # 이미 PlaceInfo가 있는 place_id — 신규 생성/갱신 판단용(refresh_info=False면 있는 건 건너뜀)
    has_info = set(
        PlaceInfo.objects.filter(place_id__in=[pk for pk, _, _ in targets]).values_list("place_id", flat=True)
    )

    for pk, content_id, ctype in targets:
        try:
            intro = api.detail_intro(content_id, ctype)
        except AllKeysExhaustedError:
            summary.aborted = True
            logger.error(
                "detailIntro2 백필: 모든 키 한도 소진 — %d건 처리 후 중단(다음 실행에서 재개)", summary.processed
            )
            break
        except TourApiError as exc:
            summary.errors += 1
            logger.warning("detailIntro2 백필 호출 실패 content_id=%s: %s", content_id, exc)
            continue
        summary.processed += 1

        # (1) tel — infocenter*에서 채운다(빈 곳만이 대상이므로 덮어쓰기 우려 없음)
        tel = _clean_tel((intro or {}).get(INFOCENTER_KEY[ctype]))
        if tel is None:
            summary.tel_missing += 1
        else:
            if not dry_run:
                Place.objects.filter(pk=pk).update(tel=tel)
            summary.tel_updated += 1

        # (2) PlaceInfo — 누락분 생성(refresh_info면 기존도 갱신)
        if intro is not None:
            info_exists = pk in has_info
            if not info_exists or refresh_info:
                defaults = build_place_info_defaults(ctype, intro)
                if defaults is not None:
                    if not dry_run:
                        PlaceInfo.objects.update_or_create(place_id=pk, defaults=defaults)
                    if info_exists:
                        summary.info_refreshed += 1
                    else:
                        summary.info_created += 1

    logger.info(
        "detailIntro2 백필 완료: 대상 %d·처리 %d·tel채움 %d·tel없음 %d·info생성 %d·info갱신 %d·실패 %d·중단 %s",
        summary.target,
        summary.processed,
        summary.tel_updated,
        summary.tel_missing,
        summary.info_created,
        summary.info_refreshed,
        summary.errors,
        summary.aborted,
    )
    return summary


#: 정제 대상 PlaceInfo 자유 텍스트 필드(boolean 제외). _clean_info_text를 태운다.
PLACE_INFO_TEXT_FIELDS: tuple[str, ...] = (
    "operating_hours",
    "closed_days",
    "admission_fee",
    "spend_time",
    "discount_info",
    "accom_count",
)


@dataclass
class CleanInfoSummary:
    """기존 PlaceInfo 텍스트 정제 백필 결과 요약."""

    scanned: int = 0  # 조회한 PlaceInfo 행 수
    changed_rows: int = 0  # 한 필드 이상 값이 바뀐 행 수
    changed_fields: int = 0  # 값이 바뀐 (행·필드) 총 개수


def clean_existing_place_info(*, dry_run: bool = False, batch_size: int = 500) -> CleanInfoSummary:
    """이미 저장된 PlaceInfo 자유 텍스트를 _clean_info_text로 재정규화한다(멱등).

    수집 시점 정제(build_place_info_defaults)는 이후 수집분에만 적용되므로, 기존 행의 <br> 등 마크업은
    이 백필로 정리한다. 값이 실제로 바뀐 행만 bulk_update한다(이미 깨끗한 값은 동일하게 나와 건너뜀).
    커서와 쓰기 동시 진행을 피하려고 변경 대상을 먼저 모은 뒤 일괄 갱신한다.
    """
    summary = CleanInfoSummary()
    to_update: list[PlaceInfo] = []
    for info in PlaceInfo.objects.all().iterator(chunk_size=2000):
        summary.scanned += 1
        dirty = False
        for field in PLACE_INFO_TEXT_FIELDS:
            current = getattr(info, field)
            cleaned = _clean_info_text(current)
            if cleaned != current:
                setattr(info, field, cleaned)
                summary.changed_fields += 1
                dirty = True
        if dirty:
            summary.changed_rows += 1
            to_update.append(info)

    if not dry_run:
        for start in range(0, len(to_update), batch_size):
            PlaceInfo.objects.bulk_update(to_update[start : start + batch_size], list(PLACE_INFO_TEXT_FIELDS))

    logger.info(
        "PlaceInfo 텍스트 정제%s: 조회 %d·변경행 %d·변경필드 %d",
        " (dry-run)" if dry_run else "",
        summary.scanned,
        summary.changed_rows,
        summary.changed_fields,
    )
    return summary
