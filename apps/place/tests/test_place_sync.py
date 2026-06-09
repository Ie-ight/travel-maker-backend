"""place_sync 수집 오케스트레이션 테스트.

값 정규화(§3-4,5)·필드 매핑(§4)·이미지 정책(§4)·수집 정책(§7)·멱등성을 검증한다.
외부 호출은 FakeClient 주입으로 대체한다(실제 API 미사용).
"""

from decimal import Decimal
from typing import Any

import pytest

from apps.place.models import Place, PlaceImage, PlaceInfo
from apps.place.services.place_sync import (
    SyncSummary,
    _blank_to_none,
    _clean_homepage,
    _clean_info_text,
    _clean_tel,
    _to_bool,
    _to_decimal,
    backfill_details,
    build_place_defaults,
    build_place_info_defaults,
    save_images,
    sync_all,
    sync_area,
    sync_incremental,
)
from apps.place.services.tour_api import AllKeysExhaustedError, TourApiError

LIST_ITEM = {
    "contentid": "2750143",
    "contenttypeid": "14",
    "title": "가가책방",
    "addr1": "충청남도 공주시 당간지주길 10 (반죽동)",
    "addr2": "",
    "tel": "",
    "zipcode": "32549",
    "mapx": "127.1219749520",
    "mapy": "36.4521187744",
    "firstimage": "http://tong.visitkorea.or.kr/cms/resource/06/3564906_image2_1.jpg",
    "firstimage2": "http://tong.visitkorea.or.kr/cms/resource/06/3564906_image3_1.jpg",
    "lclsSystm1": "VE",
    "lclsSystm2": "VE12",
    "lclsSystm3": "VE120100",
}
LIST_ITEM_NO_IMAGE = {
    "contentid": "999",
    "contenttypeid": "14",
    "title": "이미지없는곳",
    "addr1": "서울특별시 중구",
    "mapx": "126.9",
    "mapy": "37.5",
    "firstimage": "",
}
COMMON_ITEM = {
    "contentid": "2750143",
    "overview": "가가책방은 공주시 최초의 동네 책방이다.",
    "homepage": '<a href="https://brunch.co.kr/@captaindrop" target="_blank">https://brunch.co.kr/@captaindrop</a>',
}
IMAGE_ITEMS = [
    {"originimgurl": "http://img/a_origin.jpg", "smallimageurl": "http://img/a_small.jpg"},
    {"originimgurl": "http://img/b_origin.jpg", "smallimageurl": "http://img/b_small.jpg"},
]
# 명세 §3 detailIntro2 실제 응답 예시 (type 14 가가책방)
INTRO_ITEM_14 = {
    "contentid": "2750143",
    "scale": "",
    "usefee": "1인 5,000원",
    "discountinfo": "",
    "spendtime": "",
    "parkingfee": "",
    "infocenterculture": "0507-1486-4982",
    "accomcountculture": "",
    "usetimeculture": "07:00~24:00",
    "restdateculture": "연중무휴",
    "parkingculture": "불가능",
    "chkbabycarriageculture": "",
    "chkpetculture": "",
    "chkcreditcardculture": "",
}
LIST_ITEM_FESTIVAL = {  # 매핑 없는 타입(15 축제)
    "contentid": "888",
    "contenttypeid": "15",
    "title": "어느축제",
    "addr1": "부산광역시",
    "mapx": "129.0",
    "mapy": "35.1",
    "firstimage": "http://img/festival.jpg",
}


class FakeClient:
    """sync_area가 호출하는 시그니처만 흉내내는 가짜 클라이언트."""

    def __init__(
        self,
        list_items: list[dict[str, Any]],
        *,
        common_by_id: dict[int, dict[str, Any]] | None = None,
        images_by_id: dict[int, list[dict[str, Any]]] | None = None,
        intro_by_id: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        self._list_items = list_items
        self._common = common_by_id or {}
        self._images = images_by_id or {}
        self._intro = intro_by_id or {}

    def area_based_list(
        self,
        content_type_id: int,
        *,
        ldong_regn_cd: str | None = None,
        num_of_rows: int = 10,
        page_no: int = 1,
        arrange: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._list_items if page_no == 1 else []

    def detail_common(self, content_id: int) -> dict[str, Any] | None:
        return self._common.get(content_id)

    def detail_image(self, content_id: int, *, image_yn: str = "Y") -> list[dict[str, Any]]:
        return self._images.get(content_id, [])

    def detail_intro(self, content_id: int, content_type_id: int) -> dict[str, Any] | None:
        return self._intro.get(content_id)


class FakePagedClient:
    """타입·페이지별 목록을 돌려주는 가짜 클라이언트(sync_all 테스트용)."""

    def __init__(
        self,
        pages_by_type: dict[int, list[list[dict[str, Any]]]],
        *,
        common_by_id: dict[int, dict[str, Any]] | None = None,
        images_by_id: dict[int, list[dict[str, Any]]] | None = None,
        intro_by_id: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        self._pages = pages_by_type
        self._common = common_by_id or {}
        self._images = images_by_id or {}
        self._intro = intro_by_id or {}
        self.list_calls: list[tuple[int, int]] = []
        self.arrange_seen: list[str | None] = []

    def area_based_list(
        self,
        content_type_id: int,
        *,
        ldong_regn_cd: str | None = None,
        num_of_rows: int = 10,
        page_no: int = 1,
        arrange: str | None = None,
    ) -> list[dict[str, Any]]:
        self.list_calls.append((content_type_id, page_no))
        self.arrange_seen.append(arrange)
        pages = self._pages.get(content_type_id, [])
        return pages[page_no - 1] if 1 <= page_no <= len(pages) else []

    def area_based_sync_list(
        self, content_type_id: int, *, num_of_rows: int = 1000, page_no: int = 1
    ) -> list[dict[str, Any]]:
        return self.area_based_list(content_type_id, num_of_rows=num_of_rows, page_no=page_no)

    def detail_common(self, content_id: int) -> dict[str, Any] | None:
        return self._common.get(content_id)

    def detail_image(self, content_id: int, *, image_yn: str = "Y") -> list[dict[str, Any]]:
        return self._images.get(content_id, [])

    def detail_intro(self, content_id: int, content_type_id: int) -> dict[str, Any] | None:
        return self._intro.get(content_id)


class TestNormalizers:
    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_is_none(self, value: Any) -> None:
        assert _blank_to_none(value) is None

    def test_strips_whitespace(self) -> None:
        assert _blank_to_none("  가가책방 ") == "가가책방"

    def test_coordinate_to_decimal(self) -> None:
        assert _to_decimal("127.1219749520") == Decimal("127.1219749520")

    @pytest.mark.parametrize("value", ["", None, "not-a-number"])
    def test_non_number_is_none(self, value: Any) -> None:
        assert _to_decimal(value) is None

    def test_homepage_extracts_url_from_anchor(self) -> None:
        assert _clean_homepage(COMMON_ITEM["homepage"]) == "https://brunch.co.kr/@captaindrop"

    def test_homepage_plain_url_kept_when_no_anchor(self) -> None:
        assert _clean_homepage("https://example.com") == "https://example.com"

    def test_homepage_blank_is_none(self) -> None:
        assert _clean_homepage("") is None

    def test_homepage_plain_text_first_url_only(self) -> None:
        raw = "공식 홈페이지 https://a.com 공식 인스타그램 https://www.instagram.com/abc"
        assert _clean_homepage(raw) == "https://a.com"

    def test_homepage_strips_trailing_hangul_without_space(self) -> None:
        raw = "공식 홈페이지 https://a.com공식 인스타그램 https://www.instagram.com/abc"
        assert _clean_homepage(raw) == "https://a.com"

    def test_homepage_keeps_hangul_idn_domain(self) -> None:
        assert _clean_homepage("https://홈페이지.kr") == "https://홈페이지.kr"

    def test_homepage_text_without_url_is_none(self) -> None:
        assert _clean_homepage("홈페이지 없음") is None


class TestCleanInfoText:
    """운영시간 등 자유 텍스트 HTML 정제(<br> → \\n, 태그 제거, 줄바꿈 정규화)."""

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_is_none(self, value: Any) -> None:
        assert _clean_info_text(value) is None

    def test_plain_single_line_unchanged(self) -> None:
        assert _clean_info_text("09:00~18:00") == "09:00~18:00"

    @pytest.mark.parametrize("br", ["<br>", "<br/>", "<br />", "<br >", "<BR>", "<vr>"])
    def test_br_variants_become_newline(self, br: str) -> None:
        # <vr>은 실데이터에 있던 <br> 오타
        assert _clean_info_text(f"오전{br}오후") == "오전\n오후"

    def test_unclosed_br_becomes_newline(self) -> None:
        # 실데이터: 닫는 > 대신 <를 친 '<br<' 타이포
        assert _clean_info_text("평일 10:00~20:30<br<주말 10:00~20:00") == "평일 10:00~20:30\n주말 10:00~20:00"

    @pytest.mark.parametrize("word", ["a<brunch>b", "a<brb"])
    def test_br_like_words_not_converted(self, word: str) -> None:
        # br/vr 뒤가 글자면 break로 보지 않는다(<brunch>는 _TAG_RE가 태그로 제거)
        assert _clean_info_text(word) == ("ab" if word == "a<brunch>b" else "a<brb")

    def test_br_with_real_newline_collapses_blank_line(self) -> None:
        # 실데이터는 대부분 '<br>\n' 형태 — 빈 줄이 생기지 않아야 한다
        raw = "[3월~10월] 09:00 ~ 18:00<br />\n[11월~2월] 09:00 ~ 17:00"
        assert _clean_info_text(raw) == "[3월~10월] 09:00 ~ 18:00\n[11월~2월] 09:00 ~ 17:00"

    def test_multiple_br_multiline(self) -> None:
        raw = "[평일]<br>\n10:00~18:00<br>\n[주말]<br>\n10:00~19:00"
        assert _clean_info_text(raw) == "[평일]\n10:00~18:00\n[주말]\n10:00~19:00"

    def test_anchor_tag_removed_keeps_inner_text(self) -> None:
        raw = '이용요금 <a href="https://x.com" target="_blank">홈페이지</a> 참조'
        assert _clean_info_text(raw) == "이용요금 홈페이지 참조"

    def test_collapses_intra_line_spaces(self) -> None:
        assert _clean_info_text("09:00   ~   18:00") == "09:00 ~ 18:00"

    def test_idempotent(self) -> None:
        raw = "[평일]<br>\n10:00~18:00"
        once = _clean_info_text(raw)
        assert _clean_info_text(once) == once


class TestBuildPlaceDefaults:
    def test_mapping_and_type_conversion(self) -> None:
        defaults = build_place_defaults(LIST_ITEM, COMMON_ITEM)
        assert defaults["place_name"] == "가가책방"
        assert defaults["content_type_id"] == 14
        assert defaults["latitude"] == Decimal("36.4521187744")
        assert defaults["longitude"] == Decimal("127.1219749520")
        assert defaults["address_detail"] is None  # addr2 "" → None
        assert defaults["tel"] is None  # tel "" → None
        assert defaults["description"] == COMMON_ITEM["overview"]
        assert defaults["homepage"] == "https://brunch.co.kr/@captaindrop"
        assert defaults["lcls_systm1"] == "VE"

    def test_maps_without_common(self) -> None:
        defaults = build_place_defaults(LIST_ITEM, None)
        assert defaults["description"] is None
        assert defaults["homepage"] is None

    def test_maps_modifiedtime(self) -> None:
        # 단계 7: 목록 modifiedtime → source_modified_at, is_active=True
        defaults = build_place_defaults({**LIST_ITEM, "modifiedtime": "20260101120000"}, None)
        assert defaults["source_modified_at"] == "20260101120000"
        assert defaults["is_active"] is True

    def test_tel_from_intro_infocenter(self) -> None:
        # 목록 tel은 비어 있어도 detailIntro2 infocenter*(타입14=infocenterculture)에서 채운다
        defaults = build_place_defaults(LIST_ITEM, COMMON_ITEM, INTRO_ITEM_14)
        assert defaults["tel"] == "0507-1486-4982"

    def test_tel_falls_back_to_list_tel_when_intro_empty(self) -> None:
        # 축제 등 detailIntro2 미호출(intro=None) 타입은 목록 tel을 그대로 쓴다
        defaults = build_place_defaults({**LIST_ITEM, "tel": "051-740-3210"}, COMMON_ITEM, None)
        assert defaults["tel"] == "051-740-3210"

    def test_tel_falls_back_to_list_tel_when_intro_blank(self) -> None:
        intro = {**INTRO_ITEM_14, "infocenterculture": ""}
        defaults = build_place_defaults({**LIST_ITEM, "tel": "051-740-3210"}, COMMON_ITEM, intro)
        assert defaults["tel"] == "051-740-3210"


class TestCleanTel:
    @pytest.mark.parametrize(
        "raw",
        ["062-365-8733", "02-3435-0400", "031-6193-2068", "0507-1431-7040", "1899-2154"],
    )
    def test_valid_number_unchanged(self, raw: str) -> None:
        assert _clean_tel(raw) == raw

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0614718500", "061-471-8500"),  # 0XX 지역 10자리
            ("021234567", "02-123-4567"),  # 서울 9자리
            ("0212345678", "02-1234-5678"),  # 서울 10자리
            ("01012345678", "010-1234-5678"),  # 휴대폰 11자리
            ("07012345678", "070-1234-5678"),  # 070 11자리
            ("050712345678", "0507-1234-5678"),  # 안심번호 4자리 국번 12자리
        ],
    )
    def test_normalizes_number_without_hyphen(self, raw: str, expected: str) -> None:
        assert _clean_tel(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("02-360- 4351", "02-360-4351"), ("031 -770- 1001", "031-770-1001")],
    )
    def test_fixes_space_around_hyphen(self, raw: str, expected: str) -> None:
        assert _clean_tel(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("031-770-1001~2", "031-770-1001"),  # 내선 ~N 제외
            ("044-850-0591~0594", "044-850-0591"),
            ("055-340-7900~01", "055-340-7900"),
        ],
    )
    def test_excludes_extension(self, raw: str, expected: str) -> None:
        assert _clean_tel(raw) == expected

    def test_keeps_number_excludes_label(self) -> None:
        assert _clean_tel("광주광역시 관광안내소 062-365-8733") == "062-365-8733"
        assert _clean_tel("1577-0072 익산시 민원콜센터") == "1577-0072"

    def test_excludes_trailing_email(self) -> None:
        assert _clean_tel("033-644-1239, soohotel2005@gmail.com") == "033-644-1239"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("010-4753-2731 / 033-333-8523", "010-4753-2731"),  # 완전한 둘째 번호 제외
            ("061-536-2727, 010-9626-5848", "061-536-2727"),
            ("02-3700-3900<br>02-3700-3901", "02-3700-3900"),
            ("031-770-1072, 1079", "031-770-1072"),  # 축약 둘째 번호 제외
            ("02-2153-0310, 0311 (12:00~13:00 점심시간)", "02-2153-0310"),  # 시간 메모 제외
        ],
    )
    def test_multiple_numbers_first_only(self, raw: str, expected: str) -> None:
        assert _clean_tel(raw) == expected

    @pytest.mark.parametrize("value", ["", "   ", None, "관광안내소 참조", "홈페이지 참조"])
    def test_no_number_is_none(self, value: Any) -> None:
        assert _clean_tel(value) is None


class TestToBool:
    @pytest.mark.parametrize("value", ["불가", "불가능", "주차 불가능"])
    def test_contains_bulga_is_false(self, value: str) -> None:
        assert _to_bool(value) is False

    @pytest.mark.parametrize("value", ["없음", "유모차 없음", "주차공간 없음"])
    def test_contains_eopseum_is_false(self, value: str) -> None:
        # 실데이터에서 "없음"은 해당 옵션이 없다는 뜻 → 불가(False)
        assert _to_bool(value) is False

    @pytest.mark.parametrize("value", ["가능", "주차 가능", "가능 (약 소형 61대)", "있음", "Y"])
    def test_has_value_is_true(self, value: str) -> None:
        assert _to_bool(value) is True

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_is_none(self, value: Any) -> None:
        assert _to_bool(value) is None


class TestBuildPlaceInfoDefaults:
    def test_type14_mapping_and_boolean_normalization(self) -> None:
        # 명세 §8 가가책방 예시: 주차 불가, 유료 입장, 반려동물·유아·카드 정보 없음(None)
        defaults = build_place_info_defaults(14, INTRO_ITEM_14)
        assert defaults is not None
        assert defaults["operating_hours"] == "07:00~24:00"
        assert defaults["closed_days"] == "연중무휴"
        assert defaults["parking"] is False  # "불가능"
        assert defaults["admission_fee"] == "1인 5,000원"
        assert defaults["pet"] is None
        assert defaults["baby_carriage"] is None
        assert defaults["credit_card"] is None
        assert defaults["spend_time"] is None  # "" → None
        assert defaults["accom_count"] is None

    def test_unmapped_type_is_none(self) -> None:
        assert build_place_info_defaults(15, {"eventstartdate": "20260601"}) is None

    def test_lodging_operating_hours_combined(self) -> None:
        # 숙박(32)은 checkin/checkout을 operating_hours 하나로 합친다
        defaults = build_place_info_defaults(
            32, {"checkintime": "15:00", "checkouttime": "11:00", "parkinglodging": "가능"}
        )
        assert defaults is not None
        assert defaults["operating_hours"] == "체크인 15:00 / 체크아웃 11:00"
        assert defaults["parking"] is True

    def test_lodging_combines_with_checkout_only(self) -> None:
        defaults = build_place_info_defaults(32, {"checkintime": "", "checkouttime": "11:00"})
        assert defaults is not None
        assert defaults["operating_hours"] == "체크아웃 11:00"

    def test_lodging_none_when_both_missing(self) -> None:
        defaults = build_place_info_defaults(32, {"checkintime": "", "checkouttime": ""})
        assert defaults is not None
        assert defaults["operating_hours"] is None


@pytest.mark.django_db
class TestSaveImages:
    def _place(self) -> Place:
        return Place.objects.create(place_name="p", content_id=1, content_type_id=14)

    def test_saves_detail_image_results(self) -> None:
        place = self._place()
        saved = save_images(place, IMAGE_ITEMS, firstimage="fi.jpg", firstimage2="fi2.jpg")
        assert saved == 2
        images = list(place.images.all())
        assert images[0].image_url == "http://img/a_origin.jpg"
        assert images[0].thumbnail_url == "http://img/a_small.jpg"
        assert images[0].is_main is True
        assert images[1].is_main is False

    def test_falls_back_to_firstimage_without_detail_image(self) -> None:
        place = self._place()
        saved = save_images(place, [], firstimage="http://img/first.jpg", firstimage2="http://img/first2.jpg")
        assert saved == 1
        image = place.images.get()
        assert image.image_url == "http://img/first.jpg"
        assert image.thumbnail_url == "http://img/first2.jpg"
        assert image.is_main is True

    def test_uses_small_as_main_without_origin(self) -> None:
        place = self._place()
        save_images(place, [{"originimgurl": "", "smallimageurl": "http://img/only_small.jpg"}], firstimage="x")
        assert place.images.get().image_url == "http://img/only_small.jpg"

    def test_skips_when_both_empty(self) -> None:
        place = self._place()
        saved = save_images(place, [{"originimgurl": "", "smallimageurl": ""}], firstimage="x")
        assert saved == 0
        assert place.images.count() == 0


@pytest.mark.django_db
class TestSyncArea:
    def test_skips_item_without_firstimage(self) -> None:
        client = FakeClient([LIST_ITEM, LIST_ITEM_NO_IMAGE], common_by_id={2750143: COMMON_ITEM})
        summary = sync_area(14, client=client)
        assert summary.fetched == 2
        assert summary.skipped_no_image == 1
        assert summary.created == 1
        assert Place.objects.count() == 1
        assert not Place.objects.filter(content_id=999).exists()

    def test_save_result(self) -> None:
        client = FakeClient(
            [LIST_ITEM],
            common_by_id={2750143: COMMON_ITEM},
            images_by_id={2750143: IMAGE_ITEMS},
        )
        summary = sync_area(14, client=client)
        assert summary.images_saved == 2
        place = Place.objects.get(content_id=2750143)
        assert place.description == COMMON_ITEM["overview"]
        assert place.homepage == "https://brunch.co.kr/@captaindrop"
        assert place.latitude == Decimal("36.4521187744")
        assert place.address_detail is None
        assert place.images.count() == 2

    def test_detail_without_image_falls_back_to_firstimage(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM})  # images 없음
        sync_area(14, client=client)
        image = Place.objects.get(content_id=2750143).images.get()
        assert image.image_url == LIST_ITEM["firstimage"]
        assert image.thumbnail_url == LIST_ITEM["firstimage2"]

    def test_idempotent_update_on_rerun(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM}, images_by_id={2750143: IMAGE_ITEMS})
        first = sync_area(14, client=client)
        second = sync_area(14, client=client)
        assert first.created == 1 and first.updated == 0
        assert second.created == 0 and second.updated == 1
        assert Place.objects.count() == 1
        assert PlaceImage.objects.filter(place__content_id=2750143).count() == 2  # 중복 저장 없음

    def test_dry_run_does_not_save(self) -> None:
        client = FakeClient([LIST_ITEM, LIST_ITEM_NO_IMAGE], common_by_id={2750143: COMMON_ITEM})
        summary = sync_area(14, client=client, dry_run=True)
        assert summary.fetched == 2
        assert summary.skipped_no_image == 1
        assert summary.created == 0
        assert Place.objects.count() == 0

    def test_saves_place_info(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM}, intro_by_id={2750143: INTRO_ITEM_14})
        summary = sync_area(14, client=client)
        assert summary.info_saved == 1
        info = PlaceInfo.objects.get(place__content_id=2750143)
        assert info.parking is False  # "불가능"
        assert info.admission_fee == "1인 5,000원"
        assert info.operating_hours == "07:00~24:00"
        assert info.pet is None

    def test_unmapped_type_skips_place_info(self) -> None:
        # 축제(15)는 매핑 없음 → detailIntro2 미호출, PlaceInfo 생성 안 함 (Place는 저장)
        client = FakeClient([LIST_ITEM_FESTIVAL], intro_by_id={888: INTRO_ITEM_14})
        summary = sync_area(15, client=client)
        assert summary.created == 1
        assert summary.info_saved == 0
        assert PlaceInfo.objects.count() == 0

    def test_place_info_idempotent_on_rerun(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM}, intro_by_id={2750143: INTRO_ITEM_14})
        sync_area(14, client=client)
        sync_area(14, client=client)
        assert PlaceInfo.objects.filter(place__content_id=2750143).count() == 1

    def test_does_not_save_when_detail_call_fails(self) -> None:
        # detail 호출이 실패(429 등)하면 degraded 레코드를 만들지 않고 건너뛴다(다음 run 재시도).
        class _RaisingClient(FakeClient):
            def detail_common(self, content_id: int) -> dict[str, Any] | None:
                raise TourApiError("429 Too Many Requests", code="429", retryable=True)

        client = _RaisingClient([LIST_ITEM])
        summary = sync_area(14, client=client)
        assert summary.skipped_detail_failed == 1
        assert summary.created == 0
        assert Place.objects.count() == 0  # 미완성 레코드 저장 안 됨

    def test_rolls_back_and_skips_on_db_failure(self, monkeypatch: Any) -> None:
        # 한 레코드의 DB 오류가 전체 run을 중단시키지 않고, 부분 저장 없이 스킵된다.
        from django.db import DatabaseError

        from apps.place.services import place_sync

        def _boom(*args: Any, **kwargs: Any) -> None:
            raise DatabaseError("value too long")

        monkeypatch.setattr(place_sync.PlaceInfo.objects, "update_or_create", _boom)
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM}, intro_by_id={2750143: INTRO_ITEM_14})
        summary = sync_area(14, client=client)
        assert summary.skipped_save_failed == 1
        assert summary.created == 0
        assert Place.objects.count() == 0  # 트랜잭션 롤백 → 부분 저장 없음

    def test_summary_defaults(self) -> None:
        assert SyncSummary() == SyncSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


@pytest.mark.django_db
class TestSyncAll:
    """대량 적재 오케스트레이션(단계 6): 다중 타입·끝까지 페이지네이션·재개·상한."""

    def test_iterates_and_accumulates_multiple_types(self) -> None:
        item12 = {**LIST_ITEM, "contentid": "111", "contenttypeid": "12"}
        item14 = {**LIST_ITEM, "contentid": "222", "contenttypeid": "14"}
        client = FakePagedClient(
            {12: [[item12]], 14: [[item14]]},
            common_by_id={111: COMMON_ITEM, 222: COMMON_ITEM},
        )
        summary = sync_all([12, 14], num_of_rows=1, client=client)
        assert summary.created == 2
        assert Place.objects.filter(content_id__in=[111, 222]).count() == 2

    def test_paginates_to_end(self) -> None:
        a = {**LIST_ITEM, "contentid": "1"}
        b = {**LIST_ITEM, "contentid": "2"}
        c = {**LIST_ITEM, "contentid": "3"}
        # page1 가득(2건)·page2 미만(1건)=마지막 → page3 호출 안 함
        client = FakePagedClient({14: [[a, b], [c]]}, common_by_id={1: COMMON_ITEM, 2: COMMON_ITEM, 3: COMMON_ITEM})
        summary = sync_all([14], num_of_rows=2, client=client)
        assert summary.created == 3
        assert client.list_calls == [(14, 1), (14, 2)]

    def test_skip_existing_skips_existing(self) -> None:
        Place.objects.create(content_id=555, content_type_id=14, place_name="기존")
        existing = {**LIST_ITEM, "contentid": "555"}
        new = {**LIST_ITEM, "contentid": "666"}
        client = FakePagedClient({14: [[existing, new]]}, common_by_id={666: COMMON_ITEM})
        summary = sync_all([14], num_of_rows=2, skip_existing=True, client=client)
        assert summary.skipped_existing == 1
        assert summary.created == 1
        assert Place.objects.filter(content_id=666).exists()

    def test_max_pages_limit(self) -> None:
        a = {**LIST_ITEM, "contentid": "1"}
        b = {**LIST_ITEM, "contentid": "2"}
        client = FakePagedClient({14: [[a], [b]]}, common_by_id={1: COMMON_ITEM, 2: COMMON_ITEM})
        summary = sync_all([14], num_of_rows=1, max_pages=1, client=client)
        assert client.list_calls == [(14, 1)]  # 1페이지에서 멈춤
        assert summary.created == 1

    def test_passes_arrange_to_list_call(self) -> None:
        # arrange="C"(수정일순)가 area_based_list까지 전달되는지
        item = {**LIST_ITEM, "contentid": "1"}
        client = FakePagedClient({14: [[item]]}, common_by_id={1: COMMON_ITEM})
        sync_all([14], num_of_rows=1, max_pages=1, arrange="C", client=client)
        assert client.arrange_seen == ["C"]

    def test_aborts_run_when_all_keys_exhausted(self) -> None:
        # 목록 호출이 AllKeysExhaustedError면 해당 타입만 스킵하지 않고 run 전체가 중단된다.
        attempted: list[int] = []

        class _ExhaustedClient(FakePagedClient):
            def area_based_list(self, content_type_id: int, **kwargs: Any) -> list[dict[str, Any]]:
                attempted.append(content_type_id)
                raise AllKeysExhaustedError("모든 키 한도 소진", code="22")

        client = _ExhaustedClient({12: [[LIST_ITEM]], 14: [[LIST_ITEM]]})
        with pytest.raises(AllKeysExhaustedError):
            sync_all([12, 14], num_of_rows=1, client=client)
        assert attempted == [12]  # 첫 타입에서 중단 → 다음 타입(14)은 시도조차 안 함


@pytest.mark.django_db
class TestSyncIncremental:
    """증분 동기화(단계 7): 신규·변경·미변경·소프트삭제·멱등."""

    @staticmethod
    def _item(cid: str, *, showflag: str = "1", modifiedtime: str = "20260101000000", **over: Any) -> dict[str, Any]:
        return {**LIST_ITEM, "contentid": cid, "showflag": showflag, "modifiedtime": modifiedtime, **over}

    def test_creates_new(self) -> None:
        client = FakePagedClient({14: [[self._item("1001")]]}, common_by_id={1001: COMMON_ITEM})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.created == 1
        p = Place.objects.get(content_id=1001)
        assert p.source_modified_at == "20260101000000"
        assert p.is_active is True

    def test_updates_changed(self) -> None:
        Place.objects.create(
            content_id=1002, content_type_id=14, place_name="옛이름", source_modified_at="20240101000000"
        )
        item = self._item("1002", title="새이름", modifiedtime="20260101000000")
        client = FakePagedClient({14: [[item]]}, common_by_id={1002: COMMON_ITEM})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.updated == 1 and summary.created == 0
        p = Place.objects.get(content_id=1002)
        assert p.place_name == "새이름"
        assert p.source_modified_at == "20260101000000"

    def test_skips_unchanged(self) -> None:
        Place.objects.create(
            content_id=1003, content_type_id=14, place_name="그대로", source_modified_at="20260101000000"
        )
        client = FakePagedClient({14: [[self._item("1003", modifiedtime="20260101000000")]]})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.skipped_unchanged == 1
        assert summary.created == 0 and summary.updated == 0
        assert Place.objects.get(content_id=1003).place_name == "그대로"  # detail 미호출

    def test_showflag0_soft_deletes(self) -> None:
        Place.objects.create(content_id=1004, content_type_id=14, place_name="삭제될곳")
        client = FakePagedClient({14: [[self._item("1004", showflag="0")]]})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.deactivated == 1
        assert Place.objects.get(content_id=1004).is_active is False

    def test_showflag0_ignored_when_not_in_db(self) -> None:
        client = FakePagedClient({14: [[self._item("9999", showflag="0")]]})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.deactivated == 0
        assert Place.objects.count() == 0

    def test_dry_run_does_not_save(self) -> None:
        Place.objects.create(content_id=1005, content_type_id=14, place_name="x")
        client = FakePagedClient({14: [[self._item("1005", showflag="0")]]})
        summary = sync_incremental([14], num_of_rows=1, dry_run=True, client=client)
        assert summary.deactivated == 1  # 카운트는 됨
        assert Place.objects.get(content_id=1005).is_active is True  # 저장 안 됨

    def test_idempotent_rerun_second_unchanged(self) -> None:
        client = FakePagedClient({14: [[self._item("1006")]]}, common_by_id={1006: COMMON_ITEM})
        first = sync_incremental([14], num_of_rows=1, client=client)
        second = sync_incremental([14], num_of_rows=1, client=client)
        assert first.created == 1
        assert second.created == 0 and second.skipped_unchanged == 1  # baseline 저장돼 두 번째는 스킵


@pytest.mark.django_db
class TestBackfillDetails:
    def _place(self, content_id: int, *, content_type_id: int = 14, tel: str | None = None) -> Place:
        return Place.objects.create(
            content_id=content_id, content_type_id=content_type_id, place_name=f"P{content_id}", tel=tel
        )

    def test_fills_empty_tel_from_infocenter(self) -> None:
        self._place(101)
        self._place(102)
        client = FakeClient(
            [],
            intro_by_id={
                101: {**INTRO_ITEM_14, "infocenterculture": "042-280-2114"},
                102: {**INTRO_ITEM_14, "infocenterculture": "광주광역시 관광안내소 062-365-8733"},
            },
        )
        summary = backfill_details(client=client)
        assert summary.target == 2
        assert summary.tel_updated == 2
        assert Place.objects.get(content_id=101).tel == "042-280-2114"
        # 라벨은 제외되고 번호만 저장된다
        assert Place.objects.get(content_id=102).tel == "062-365-8733"

    def test_not_targeted_when_tel_exists(self) -> None:
        self._place(101, tel="02-1234-5678")
        client = FakeClient([], intro_by_id={101: {**INTRO_ITEM_14, "infocenterculture": "다른번호"}})
        summary = backfill_details(client=client)
        assert summary.target == 0
        assert Place.objects.get(content_id=101).tel == "02-1234-5678"

    def test_excludes_festival(self) -> None:
        # 축제(15)는 INFOCENTER_KEY 없음 → 대상에서 빠진다
        self._place(201, content_type_id=15)
        client = FakeClient([], intro_by_id={201: {"infocenterculture": "x"}})
        summary = backfill_details(client=client)
        assert summary.target == 0

    def test_cannot_fill_tel_when_infocenter_empty(self) -> None:
        self._place(101)
        client = FakeClient([], intro_by_id={101: {**INTRO_ITEM_14, "infocenterculture": ""}})
        summary = backfill_details(client=client)
        assert summary.processed == 1
        assert summary.tel_missing == 1
        assert summary.tel_updated == 0
        assert Place.objects.get(content_id=101).tel is None

    def test_creates_missing_place_info(self) -> None:
        place = self._place(101)
        assert not PlaceInfo.objects.filter(place=place).exists()
        client = FakeClient([], intro_by_id={101: INTRO_ITEM_14})
        summary = backfill_details(client=client)
        assert summary.info_created == 1
        info = PlaceInfo.objects.get(place=place)
        assert info.parking is False  # "불가능"
        assert info.admission_fee == "1인 5,000원"

    def test_existing_place_info_untouched_by_default(self) -> None:
        place = self._place(101)
        PlaceInfo.objects.create(place=place, admission_fee="기존값")
        client = FakeClient([], intro_by_id={101: INTRO_ITEM_14})
        summary = backfill_details(client=client)
        assert summary.info_created == 0
        assert summary.info_refreshed == 0
        assert PlaceInfo.objects.get(place=place).admission_fee == "기존값"  # 그대로

    def test_refresh_info_updates_existing_place_info(self) -> None:
        place = self._place(101)
        PlaceInfo.objects.create(place=place, admission_fee="기존값")
        client = FakeClient([], intro_by_id={101: INTRO_ITEM_14})
        summary = backfill_details(client=client, refresh_info=True)
        assert summary.info_refreshed == 1
        assert PlaceInfo.objects.get(place=place).admission_fee == "1인 5,000원"  # 갱신됨

    def test_dry_run_does_not_save(self) -> None:
        place = self._place(101)
        client = FakeClient([], intro_by_id={101: {**INTRO_ITEM_14, "infocenterculture": "042-280-2114"}})
        summary = backfill_details(client=client, dry_run=True)
        assert summary.tel_updated == 1 and summary.info_created == 1  # 카운트는 됨
        assert Place.objects.get(content_id=101).tel is None
        assert not PlaceInfo.objects.filter(place=place).exists()

    def test_applies_limit(self) -> None:
        for cid in (101, 102, 103):
            self._place(cid)
        client = FakeClient(
            [], intro_by_id={c: {**INTRO_ITEM_14, "infocenterculture": "02-3700-3900"} for c in (101, 102, 103)}
        )
        summary = backfill_details(limit=2, client=client)
        assert summary.target == 2
        assert summary.tel_updated == 2

    def test_aborts_and_resumable_when_keys_exhausted(self) -> None:
        self._place(101)
        self._place(102)

        class _ExhaustedClient(FakeClient):
            def detail_intro(self, content_id: int, content_type_id: int) -> dict[str, Any] | None:
                raise AllKeysExhaustedError("소진")

        summary = backfill_details(client=_ExhaustedClient([]))
        assert summary.aborted is True
        assert summary.tel_updated == 0
        assert Place.objects.get(content_id=101).tel is None  # 저장된 것 없음 → 다음 실행에서 재대상
