"""PlaceFeature 덤프/적재(content_id 매칭) 테스트."""

from typing import Any

import pytest
from django.core.management import call_command

from apps.place.models import Place, PlaceFeature
from apps.place.services.place_feature_dump_service import (
    load_place_features,
    serialize_place_features,
)


def make_place(content_id: int) -> Place:
    return Place.objects.create(
        place_name=f"장소 {content_id}",
        content_id=content_id,
        content_type_id=14,
        address_primary="충청남도 공주시",
        lcls_systm1="VE",
    )


@pytest.mark.django_db
class TestSerializePlaceFeatures:
    def test_serializes_vectors_to_plain_floats(self) -> None:
        place = make_place(content_id=1)
        PlaceFeature.objects.create(
            place=place, style_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6], content_vector=[0.7] * 1024
        )

        rows = list(serialize_place_features(PlaceFeature.objects.select_related("place")))

        assert len(rows) == 1
        row = rows[0]
        assert row["content_id"] == 1
        assert row["style_vector"] is not None
        assert all(isinstance(v, float) for v in row["style_vector"])
        assert row["style_vector"][0] == pytest.approx(0.1, abs=1e-5)
        assert row["content_vector"] is not None
        assert row["content_vector"][0] == pytest.approx(0.7, abs=1e-5)

    def test_serializes_null_style_vector(self) -> None:
        place = make_place(content_id=2)
        PlaceFeature.objects.create(place=place, style_vector=None, content_vector=[0.5] * 1024)

        rows = list(serialize_place_features(PlaceFeature.objects.select_related("place")))

        assert rows[0]["style_vector"] is None
        assert rows[0]["content_vector"] is not None


@pytest.mark.django_db
class TestLoadPlaceFeatures:
    def test_matches_by_content_id_and_updates(self) -> None:
        place = make_place(content_id=10)
        PlaceFeature.objects.create(place=place, style_vector=[0.0] * 6, content_vector=[0.0] * 1024)

        rows = [{"content_id": 10, "style_vector": [0.9] * 6, "content_vector": [0.8] * 1024}]
        summary = load_place_features(rows)

        assert summary.matched == 1
        assert summary.unmatched == 0
        feature = PlaceFeature.objects.get(place=place)
        assert float(feature.style_vector[0]) == pytest.approx(0.9, abs=1e-5)
        assert float(feature.content_vector[0]) == pytest.approx(0.8, abs=1e-5)

    def test_creates_place_feature_when_missing(self) -> None:
        place = make_place(content_id=20)

        rows = [{"content_id": 20, "style_vector": None, "content_vector": [0.3] * 1024}]
        summary = load_place_features(rows)

        assert summary.matched == 1
        feature = PlaceFeature.objects.get(place=place)
        assert feature.style_vector is None
        assert float(feature.content_vector[0]) == pytest.approx(0.3, abs=1e-5)

    def test_unmatched_content_id_is_skipped(self) -> None:
        rows = [{"content_id": 99999, "style_vector": None, "content_vector": [0.1] * 1024}]
        summary = load_place_features(rows)

        assert summary.matched == 0
        assert summary.unmatched == 1
        assert not PlaceFeature.objects.filter(place__content_id=99999).exists()


@pytest.mark.django_db
class TestDumpAndLoadCommands:
    def test_round_trip(self, tmp_path: Any) -> None:
        place = make_place(content_id=30)
        PlaceFeature.objects.create(
            place=place, style_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6], content_vector=[0.42] * 1024
        )

        out = tmp_path / "dump.json"
        call_command("dump_place_features", f"--out={out}", "--settings=config.settings.local")
        assert out.exists()

        PlaceFeature.objects.filter(place=place).update(content_vector=None, style_vector=None)

        call_command("load_place_features", f"--in={out}", "--settings=config.settings.local")

        feature = PlaceFeature.objects.get(place=place)
        assert float(feature.content_vector[0]) == pytest.approx(0.42, abs=1e-5)
        assert float(feature.style_vector[0]) == pytest.approx(0.1, abs=1e-5)
