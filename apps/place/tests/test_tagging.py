"""결정론 태깅(단계 4) 테스트: 시드 + 지역(주소 파싱) + 편의성(PlaceInfo)."""

import pytest
from django.core.management import call_command

from apps.place.models import Place, PlaceInfo, Tag
from apps.place.services.tag_seeds import TAG_SEEDS
from apps.place.services.tagging import (
    _region_tag_name,
    assign_deterministic_tags,
    assign_facility_tags,
    assign_region_tag,
)


@pytest.fixture
def seeded() -> None:
    call_command("seed_tags")


def make_place(address_primary: str = "서울특별시 종로구", content_type_id: int = 12, content_id: int = 1) -> Place:
    return Place.objects.create(
        place_name="테스트장소",
        content_id=content_id,
        content_type_id=content_type_id,
        address_primary=address_primary,
    )


def tag_names(place: Place) -> set[str]:
    return set(place.tags.values_list("tag_name", flat=True))


@pytest.mark.django_db
class TestSeedTags:
    def test_시드_적재(self) -> None:
        call_command("seed_tags")
        assert Tag.objects.count() == sum(len(v) for v in TAG_SEEDS.values()) == 53
        assert set(Tag.objects.values_list("tag_type", flat=True).distinct()) == set(TAG_SEEDS)

    def test_재실행_멱등(self) -> None:
        call_command("seed_tags")
        call_command("seed_tags")
        assert Tag.objects.count() == 53


class TestRegionParsing:
    @pytest.mark.parametrize(
        ("addr", "expected"),
        [
            ("강원특별자치도 춘천시", "강원"),
            ("전북특별자치도 익산시", "전북"),
            ("서울특별시 종로구", "서울"),
            ("경기도 과천시", "경기"),
            ("제주특별자치도 제주시", "제주"),
            ("충청남도 공주시", "충남"),
        ],
    )
    def test_시도_파싱(self, addr: str, expected: str) -> None:
        assert _region_tag_name(addr) == expected

    @pytest.mark.parametrize("addr", ["", None, "어딘가 외국"])
    def test_미매칭은_None(self, addr: str | None) -> None:
        assert _region_tag_name(addr) is None


@pytest.mark.django_db
class TestAssignRegionTag:
    def test_지역_태그_부여(self, seeded: None) -> None:
        place = make_place("전북특별자치도 익산시")
        assert assign_region_tag(place) == "전북"
        assert tag_names(place) == {"전북"}

    def test_시드_없으면_미부여(self) -> None:  # seeded 미사용
        place = make_place("서울특별시 종로구")
        assert assign_region_tag(place) is None
        assert tag_names(place) == set()


@pytest.mark.django_db
class TestAssignFacilityTags:
    def _info(self, place: Place, **kwargs: object) -> PlaceInfo:
        return PlaceInfo.objects.create(place=place, **kwargs)

    def test_True_필드만_부여(self, seeded: None) -> None:
        place = make_place(content_type_id=14)
        self._info(place, parking=True, credit_card=True, pet=False, baby_carriage=None, admission_fee="무료")
        assert set(assign_facility_tags(place)) == {"주차 가능 여부", "카드 결제 가능", "무료 입장 여부"}

    def test_유료면_무료입장_미부여(self, seeded: None) -> None:
        place = make_place(content_type_id=14)
        self._info(place, parking=False, admission_fee="1인 5,000원")
        assert assign_facility_tags(place) == []

    def test_PlaceInfo_없으면_빈리스트(self, seeded: None) -> None:
        place = make_place(content_type_id=12)
        assert assign_facility_tags(place) == []


@pytest.mark.django_db
class TestAssignDeterministicTags:
    def test_지역_편의성_함께_부여(self, seeded: None) -> None:
        place = make_place("전북특별자치도 익산시", content_type_id=14)
        PlaceInfo.objects.create(place=place, parking=True, admission_fee="무료", credit_card=False)
        assign_deterministic_tags(place)
        assert tag_names(place) == {"전북", "주차 가능 여부", "무료 입장 여부"}

    def test_멱등_재실행(self, seeded: None) -> None:
        place = make_place("서울특별시 종로구", content_type_id=14)
        PlaceInfo.objects.create(place=place, parking=True)
        assign_deterministic_tags(place)
        assign_deterministic_tags(place)
        assert tag_names(place) == {"서울", "주차 가능 여부"}
        assert place.tags.count() == 2  # 중복 없음

    def test_AI_태그_보존(self, seeded: None) -> None:
        place = make_place("서울특별시 종로구", content_type_id=14)
        place.tags.add(Tag.objects.get(tag_name="문화"))  # 여행 스타일(AI성)
        assign_deterministic_tags(place)
        assert "문화" in tag_names(place)
        assert "서울" in tag_names(place)

    def test_PlaceInfo_변경_반영(self, seeded: None) -> None:
        place = make_place("서울특별시 종로구", content_type_id=14)
        info = PlaceInfo.objects.create(place=place, parking=True)
        assign_deterministic_tags(place)
        assert "주차 가능 여부" in tag_names(place)
        info.parking = False
        info.save()
        assign_deterministic_tags(place)
        assert "주차 가능 여부" not in tag_names(place)
        assert "서울" in tag_names(place)
