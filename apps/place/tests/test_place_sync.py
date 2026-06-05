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
    _to_bool,
    _to_decimal,
    build_place_defaults,
    build_place_info_defaults,
    save_images,
    sync_all,
    sync_area,
    sync_incremental,
)
from apps.place.services.tour_api import TourApiError

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
    def test_빈값은_None(self, value: Any) -> None:
        assert _blank_to_none(value) is None

    def test_공백제거(self) -> None:
        assert _blank_to_none("  가가책방 ") == "가가책방"

    def test_좌표_Decimal_변환(self) -> None:
        assert _to_decimal("127.1219749520") == Decimal("127.1219749520")

    @pytest.mark.parametrize("value", ["", None, "not-a-number"])
    def test_숫자아니면_None(self, value: Any) -> None:
        assert _to_decimal(value) is None

    def test_homepage_앵커에서_URL_추출(self) -> None:
        assert _clean_homepage(COMMON_ITEM["homepage"]) == "https://brunch.co.kr/@captaindrop"

    def test_homepage_앵커없으면_원문(self) -> None:
        assert _clean_homepage("https://example.com") == "https://example.com"

    def test_homepage_빈값은_None(self) -> None:
        assert _clean_homepage("") is None

    def test_homepage_평문_복수URL_첫번째만(self) -> None:
        raw = "공식 홈페이지 https://a.com 공식 인스타그램 https://www.instagram.com/abc"
        assert _clean_homepage(raw) == "https://a.com"

    def test_homepage_공백없이_붙은_한글_제거(self) -> None:
        raw = "공식 홈페이지 https://a.com공식 인스타그램 https://www.instagram.com/abc"
        assert _clean_homepage(raw) == "https://a.com"

    def test_homepage_한글IDN_도메인_보존(self) -> None:
        assert _clean_homepage("https://홈페이지.kr") == "https://홈페이지.kr"

    def test_homepage_URL없는_원문은_None(self) -> None:
        assert _clean_homepage("홈페이지 없음") is None


class TestBuildPlaceDefaults:
    def test_매핑과_타입변환(self) -> None:
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

    def test_common_없어도_매핑(self) -> None:
        defaults = build_place_defaults(LIST_ITEM, None)
        assert defaults["description"] is None
        assert defaults["homepage"] is None

    def test_modifiedtime_매핑(self) -> None:
        # 단계 7: 목록 modifiedtime → source_modified_at, is_active=True
        defaults = build_place_defaults({**LIST_ITEM, "modifiedtime": "20260101120000"}, None)
        assert defaults["source_modified_at"] == "20260101120000"
        assert defaults["is_active"] is True


class TestToBool:
    @pytest.mark.parametrize("value", ["불가", "불가능", "주차 불가능"])
    def test_불가_포함은_False(self, value: str) -> None:
        assert _to_bool(value) is False

    @pytest.mark.parametrize("value", ["없음", "유모차 없음", "주차공간 없음"])
    def test_없음_포함은_False(self, value: str) -> None:
        # 실데이터에서 "없음"은 해당 옵션이 없다는 뜻 → 불가(False)
        assert _to_bool(value) is False

    @pytest.mark.parametrize("value", ["가능", "주차 가능", "가능 (약 소형 61대)", "있음", "Y"])
    def test_값_있으면_True(self, value: str) -> None:
        assert _to_bool(value) is True

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_빈값은_None(self, value: Any) -> None:
        assert _to_bool(value) is None


class TestBuildPlaceInfoDefaults:
    def test_type14_매핑과_boolean정규화(self) -> None:
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

    def test_매핑없는_타입은_None(self) -> None:
        assert build_place_info_defaults(15, {"eventstartdate": "20260601"}) is None

    def test_숙박_운영시간_조합(self) -> None:
        # 숙박(32)은 checkin/checkout을 operating_hours 하나로 합친다
        defaults = build_place_info_defaults(
            32, {"checkintime": "15:00", "checkouttime": "11:00", "parkinglodging": "가능"}
        )
        assert defaults is not None
        assert defaults["operating_hours"] == "체크인 15:00 / 체크아웃 11:00"
        assert defaults["parking"] is True

    def test_숙박_체크아웃만_있어도_조합(self) -> None:
        defaults = build_place_info_defaults(32, {"checkintime": "", "checkouttime": "11:00"})
        assert defaults is not None
        assert defaults["operating_hours"] == "체크아웃 11:00"

    def test_숙박_둘다_없으면_None(self) -> None:
        defaults = build_place_info_defaults(32, {"checkintime": "", "checkouttime": ""})
        assert defaults is not None
        assert defaults["operating_hours"] is None


@pytest.mark.django_db
class TestSaveImages:
    def _place(self) -> Place:
        return Place.objects.create(place_name="p", content_id=1, content_type_id=14)

    def test_detailImage_결과_저장(self) -> None:
        place = self._place()
        saved = save_images(place, IMAGE_ITEMS, firstimage="fi.jpg", firstimage2="fi2.jpg")
        assert saved == 2
        images = list(place.images.all())
        assert images[0].image_url == "http://img/a_origin.jpg"
        assert images[0].thumbnail_url == "http://img/a_small.jpg"
        assert images[0].is_main is True
        assert images[1].is_main is False

    def test_detailImage_없으면_firstimage_폴백(self) -> None:
        place = self._place()
        saved = save_images(place, [], firstimage="http://img/first.jpg", firstimage2="http://img/first2.jpg")
        assert saved == 1
        image = place.images.get()
        assert image.image_url == "http://img/first.jpg"
        assert image.thumbnail_url == "http://img/first2.jpg"
        assert image.is_main is True

    def test_origin_없으면_small을_대표로(self) -> None:
        place = self._place()
        save_images(place, [{"originimgurl": "", "smallimageurl": "http://img/only_small.jpg"}], firstimage="x")
        assert place.images.get().image_url == "http://img/only_small.jpg"

    def test_둘다_빈값이면_skip(self) -> None:
        place = self._place()
        saved = save_images(place, [{"originimgurl": "", "smallimageurl": ""}], firstimage="x")
        assert saved == 0
        assert place.images.count() == 0


@pytest.mark.django_db
class TestSyncArea:
    def test_firstimage_없는_항목은_skip(self) -> None:
        client = FakeClient([LIST_ITEM, LIST_ITEM_NO_IMAGE], common_by_id={2750143: COMMON_ITEM})
        summary = sync_area(14, client=client)
        assert summary.fetched == 2
        assert summary.skipped_no_image == 1
        assert summary.created == 1
        assert Place.objects.count() == 1
        assert not Place.objects.filter(content_id=999).exists()

    def test_저장_결과_검증(self) -> None:
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

    def test_이미지없는_상세는_firstimage_폴백(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM})  # images 없음
        sync_area(14, client=client)
        image = Place.objects.get(content_id=2750143).images.get()
        assert image.image_url == LIST_ITEM["firstimage"]
        assert image.thumbnail_url == LIST_ITEM["firstimage2"]

    def test_재실행시_멱등_갱신(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM}, images_by_id={2750143: IMAGE_ITEMS})
        first = sync_area(14, client=client)
        second = sync_area(14, client=client)
        assert first.created == 1 and first.updated == 0
        assert second.created == 0 and second.updated == 1
        assert Place.objects.count() == 1
        assert PlaceImage.objects.filter(place__content_id=2750143).count() == 2  # 중복 저장 없음

    def test_dry_run은_저장하지_않음(self) -> None:
        client = FakeClient([LIST_ITEM, LIST_ITEM_NO_IMAGE], common_by_id={2750143: COMMON_ITEM})
        summary = sync_area(14, client=client, dry_run=True)
        assert summary.fetched == 2
        assert summary.skipped_no_image == 1
        assert summary.created == 0
        assert Place.objects.count() == 0

    def test_PlaceInfo_저장(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM}, intro_by_id={2750143: INTRO_ITEM_14})
        summary = sync_area(14, client=client)
        assert summary.info_saved == 1
        info = PlaceInfo.objects.get(place__content_id=2750143)
        assert info.parking is False  # "불가능"
        assert info.admission_fee == "1인 5,000원"
        assert info.operating_hours == "07:00~24:00"
        assert info.pet is None

    def test_매핑없는_타입은_PlaceInfo_미저장(self) -> None:
        # 축제(15)는 매핑 없음 → detailIntro2 미호출, PlaceInfo 생성 안 함 (Place는 저장)
        client = FakeClient([LIST_ITEM_FESTIVAL], intro_by_id={888: INTRO_ITEM_14})
        summary = sync_area(15, client=client)
        assert summary.created == 1
        assert summary.info_saved == 0
        assert PlaceInfo.objects.count() == 0

    def test_PlaceInfo_재실행_멱등(self) -> None:
        client = FakeClient([LIST_ITEM], common_by_id={2750143: COMMON_ITEM}, intro_by_id={2750143: INTRO_ITEM_14})
        sync_area(14, client=client)
        sync_area(14, client=client)
        assert PlaceInfo.objects.filter(place__content_id=2750143).count() == 1

    def test_상세호출_실패시_저장안함(self) -> None:
        # detail 호출이 실패(429 등)하면 degraded 레코드를 만들지 않고 건너뛴다(다음 run 재시도).
        class _RaisingClient(FakeClient):
            def detail_common(self, content_id: int) -> dict[str, Any] | None:
                raise TourApiError("429 Too Many Requests", code="429", retryable=True)

        client = _RaisingClient([LIST_ITEM])
        summary = sync_area(14, client=client)
        assert summary.skipped_detail_failed == 1
        assert summary.created == 0
        assert Place.objects.count() == 0  # 미완성 레코드 저장 안 됨

    def test_DB저장_실패시_롤백하고_건너뜀(self, monkeypatch: Any) -> None:
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

    def test_summary_기본값(self) -> None:
        assert SyncSummary() == SyncSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


@pytest.mark.django_db
class TestSyncAll:
    """대량 적재 오케스트레이션(단계 6): 다중 타입·끝까지 페이지네이션·재개·상한."""

    def test_여러_타입_순회_누적(self) -> None:
        item12 = {**LIST_ITEM, "contentid": "111", "contenttypeid": "12"}
        item14 = {**LIST_ITEM, "contentid": "222", "contenttypeid": "14"}
        client = FakePagedClient(
            {12: [[item12]], 14: [[item14]]},
            common_by_id={111: COMMON_ITEM, 222: COMMON_ITEM},
        )
        summary = sync_all([12, 14], num_of_rows=1, client=client)
        assert summary.created == 2
        assert Place.objects.filter(content_id__in=[111, 222]).count() == 2

    def test_끝까지_페이지네이션(self) -> None:
        a = {**LIST_ITEM, "contentid": "1"}
        b = {**LIST_ITEM, "contentid": "2"}
        c = {**LIST_ITEM, "contentid": "3"}
        # page1 가득(2건)·page2 미만(1건)=마지막 → page3 호출 안 함
        client = FakePagedClient({14: [[a, b], [c]]}, common_by_id={1: COMMON_ITEM, 2: COMMON_ITEM, 3: COMMON_ITEM})
        summary = sync_all([14], num_of_rows=2, client=client)
        assert summary.created == 3
        assert client.list_calls == [(14, 1), (14, 2)]

    def test_skip_existing은_기존_스킵(self) -> None:
        Place.objects.create(content_id=555, content_type_id=14, place_name="기존")
        existing = {**LIST_ITEM, "contentid": "555"}
        new = {**LIST_ITEM, "contentid": "666"}
        client = FakePagedClient({14: [[existing, new]]}, common_by_id={666: COMMON_ITEM})
        summary = sync_all([14], num_of_rows=2, skip_existing=True, client=client)
        assert summary.skipped_existing == 1
        assert summary.created == 1
        assert Place.objects.filter(content_id=666).exists()

    def test_max_pages_상한(self) -> None:
        a = {**LIST_ITEM, "contentid": "1"}
        b = {**LIST_ITEM, "contentid": "2"}
        client = FakePagedClient({14: [[a], [b]]}, common_by_id={1: COMMON_ITEM, 2: COMMON_ITEM})
        summary = sync_all([14], num_of_rows=1, max_pages=1, client=client)
        assert client.list_calls == [(14, 1)]  # 1페이지에서 멈춤
        assert summary.created == 1

    def test_arrange_목록호출에_전달(self) -> None:
        # arrange="C"(수정일순)가 area_based_list까지 전달되는지
        item = {**LIST_ITEM, "contentid": "1"}
        client = FakePagedClient({14: [[item]]}, common_by_id={1: COMMON_ITEM})
        sync_all([14], num_of_rows=1, max_pages=1, arrange="C", client=client)
        assert client.arrange_seen == ["C"]


@pytest.mark.django_db
class TestSyncIncremental:
    """증분 동기화(단계 7): 신규·변경·미변경·소프트삭제·멱등."""

    @staticmethod
    def _item(cid: str, *, showflag: str = "1", modifiedtime: str = "20260101000000", **over: Any) -> dict[str, Any]:
        return {**LIST_ITEM, "contentid": cid, "showflag": showflag, "modifiedtime": modifiedtime, **over}

    def test_신규_생성(self) -> None:
        client = FakePagedClient({14: [[self._item("1001")]]}, common_by_id={1001: COMMON_ITEM})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.created == 1
        p = Place.objects.get(content_id=1001)
        assert p.source_modified_at == "20260101000000"
        assert p.is_active is True

    def test_변경_갱신(self) -> None:
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

    def test_미변경_스킵(self) -> None:
        Place.objects.create(
            content_id=1003, content_type_id=14, place_name="그대로", source_modified_at="20260101000000"
        )
        client = FakePagedClient({14: [[self._item("1003", modifiedtime="20260101000000")]]})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.skipped_unchanged == 1
        assert summary.created == 0 and summary.updated == 0
        assert Place.objects.get(content_id=1003).place_name == "그대로"  # detail 미호출

    def test_showflag0_소프트삭제(self) -> None:
        Place.objects.create(content_id=1004, content_type_id=14, place_name="삭제될곳")
        client = FakePagedClient({14: [[self._item("1004", showflag="0")]]})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.deactivated == 1
        assert Place.objects.get(content_id=1004).is_active is False

    def test_showflag0_DB에없으면_무시(self) -> None:
        client = FakePagedClient({14: [[self._item("9999", showflag="0")]]})
        summary = sync_incremental([14], num_of_rows=1, client=client)
        assert summary.deactivated == 0
        assert Place.objects.count() == 0

    def test_dry_run은_저장안함(self) -> None:
        Place.objects.create(content_id=1005, content_type_id=14, place_name="x")
        client = FakePagedClient({14: [[self._item("1005", showflag="0")]]})
        summary = sync_incremental([14], num_of_rows=1, dry_run=True, client=client)
        assert summary.deactivated == 1  # 카운트는 됨
        assert Place.objects.get(content_id=1005).is_active is True  # 저장 안 됨

    def test_재실행_멱등_두번째는_미변경(self) -> None:
        client = FakePagedClient({14: [[self._item("1006")]]}, common_by_id={1006: COMMON_ITEM})
        first = sync_incremental([14], num_of_rows=1, client=client)
        second = sync_incremental([14], num_of_rows=1, client=client)
        assert first.created == 1
        assert second.created == 0 and second.skipped_unchanged == 1  # baseline 저장돼 두 번째는 스킵
