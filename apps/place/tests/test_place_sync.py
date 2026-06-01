"""place_sync 수집 오케스트레이션 테스트.

값 정규화(§3-4,5)·필드 매핑(§4)·이미지 정책(§4)·수집 정책(§7)·멱등성을 검증한다.
외부 호출은 FakeClient 주입으로 대체한다(실제 API 미사용).
"""

from decimal import Decimal
from typing import Any

import pytest

from apps.place.models import Place, PlaceImage
from apps.place.services.place_sync import (
    SyncSummary,
    _blank_to_none,
    _clean_homepage,
    _to_decimal,
    build_place_defaults,
    save_images,
    sync_area,
)

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


class FakeClient:
    """sync_area가 호출하는 시그니처만 흉내내는 가짜 클라이언트."""

    def __init__(
        self,
        list_items: list[dict[str, Any]],
        *,
        common_by_id: dict[int, dict[str, Any]] | None = None,
        images_by_id: dict[int, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._list_items = list_items
        self._common = common_by_id or {}
        self._images = images_by_id or {}

    def area_based_list(
        self,
        content_type_id: int,
        *,
        ldong_regn_cd: str | None = None,
        num_of_rows: int = 10,
        page_no: int = 1,
    ) -> list[dict[str, Any]]:
        return self._list_items if page_no == 1 else []

    def detail_common(self, content_id: int) -> dict[str, Any] | None:
        return self._common.get(content_id)

    def detail_image(self, content_id: int, *, image_yn: str = "Y") -> list[dict[str, Any]]:
        return self._images.get(content_id, [])


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

    def test_summary_기본값(self) -> None:
        assert SyncSummary() == SyncSummary(0, 0, 0, 0, 0)
