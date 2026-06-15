"""장소 텍스트 임베딩(P1.5) 테스트 — 가짜 Ollama/Gemini 클라이언트 주입(실제 API 호출 없음)."""

from typing import Any

import pytest
from django.core.management import call_command

from apps.place.models import Place, PlaceFeature
from apps.place.services.embedding_service import (
    EMBEDDING_DIM,
    EmbeddingError,
    build_embedding_text,
    embed_place,
    embed_texts,
    persist_content_vector,
)


@pytest.fixture(autouse=True)
def _default_provider_ollama(settings: Any) -> None:
    settings.EMBEDDING_PROVIDER = "ollama"


def make_place(description: str = "가가책방은 공주시 최초의 동네 책방이다.", content_id: int = 1) -> Place:
    return Place.objects.create(
        place_name="가가책방",
        content_id=content_id,
        content_type_id=14,
        description=description,
        address_primary="충청남도 공주시",
        lcls_systm1="VE",
    )


class FakeOllamaClient:
    """embed_texts가 쓰는 embed()만 흉내내는 가짜 Ollama 클라이언트."""

    def __init__(self, *, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim
        self.calls: list[dict[str, Any]] = []

    def embed(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        vectors = [[0.1] * self._dim for _ in kwargs["input"]]
        return type("Resp", (), {"embeddings": vectors})()


class FakeGeminiClient:
    """embed_texts가 쓰는 models.embed_content()만 흉내내는 가짜 Gemini 클라이언트."""

    def __init__(self, *, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim
        self.calls: list[dict[str, Any]] = []
        self.models = self

    def embed_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        embeddings = [type("Embedding", (), {"values": [0.2] * self._dim})() for _ in kwargs["contents"]]
        return type("Resp", (), {"embeddings": embeddings})()


@pytest.mark.django_db
class TestBuildEmbeddingText:
    def test_includes_title_and_lcls(self) -> None:
        text = build_embedding_text(make_place())
        assert "제목: 가가책방" in text
        assert "분류:" in text
        assert "설명: 가가책방은 공주시 최초의 동네 책방이다." in text

    def test_omits_description_when_blank(self) -> None:
        text = build_embedding_text(make_place(description=""))
        assert "설명:" not in text


@pytest.mark.django_db
class TestEmbedTexts:
    def test_empty_input_returns_empty(self) -> None:
        assert embed_texts([]) == []

    def test_ollama_returns_vectors(self) -> None:
        client = FakeOllamaClient()
        vectors = embed_texts(["a", "b"], client=client, provider="ollama")
        assert len(vectors) == 2
        assert len(vectors[0]) == EMBEDDING_DIM
        assert client.calls[0]["input"] == ["a", "b"]

    def test_gemini_returns_vectors(self) -> None:
        client = FakeGeminiClient()
        vectors = embed_texts(["a"], client=client, provider="gemini")
        assert len(vectors) == 1
        assert len(vectors[0]) == EMBEDDING_DIM

    def test_dimension_mismatch_raises(self) -> None:
        client = FakeOllamaClient(dim=512)
        with pytest.raises(EmbeddingError):
            embed_texts(["a"], client=client, provider="ollama")

    def test_embed_place_returns_single_vector(self) -> None:
        client = FakeOllamaClient()
        vector = embed_place(make_place(), client=client, provider="ollama")
        assert len(vector) == EMBEDDING_DIM


@pytest.mark.django_db
class TestPersistContentVector:
    def test_updates_existing_place_feature(self) -> None:
        place = make_place()
        PlaceFeature.objects.create(place=place, style_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6])

        persist_content_vector(place, [0.3] * EMBEDDING_DIM)

        feature = PlaceFeature.objects.get(place=place)
        assert feature.content_vector is not None
        assert float(feature.content_vector[0]) == pytest.approx(0.3, abs=1e-5)

    def test_creates_place_feature_with_null_style_vector_when_missing(self) -> None:
        place = make_place()

        persist_content_vector(place, [0.3] * EMBEDDING_DIM)

        feature = PlaceFeature.objects.get(place=place)
        assert feature.style_vector is None
        assert feature.content_vector is not None
        assert float(feature.content_vector[0]) == pytest.approx(0.3, abs=1e-5)


@pytest.mark.django_db
class TestEmbedPlacesCommand:
    def test_only_missing_includes_places_without_place_feature(self, monkeypatch: Any) -> None:
        place_with_feature = make_place(content_id=1)
        PlaceFeature.objects.create(place=place_with_feature, style_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        place_without_feature = make_place(content_id=2)  # PlaceFeature 없음 — 새로 생성되어야 함

        def fake_embed_texts(texts: list[str], **kwargs: Any) -> list[list[float]]:
            return [[0.4] * EMBEDDING_DIM for _ in texts]

        monkeypatch.setattr("apps.place.management.commands.embed_places.embed_texts", fake_embed_texts)

        call_command("embed_places", "--only-missing", "--settings=config.settings.local")

        feature = PlaceFeature.objects.get(place=place_with_feature)
        assert feature.content_vector is not None
        assert float(feature.content_vector[0]) == pytest.approx(0.4, abs=1e-5)

        new_feature = PlaceFeature.objects.get(place=place_without_feature)
        assert new_feature.style_vector is None
        assert new_feature.content_vector is not None
        assert float(new_feature.content_vector[0]) == pytest.approx(0.4, abs=1e-5)

    def test_dry_run_does_not_persist(self, monkeypatch: Any) -> None:
        place = make_place()
        PlaceFeature.objects.create(place=place, style_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6])

        def fake_embed_texts(texts: list[str], **kwargs: Any) -> list[list[float]]:
            return [[0.4] * EMBEDDING_DIM for _ in texts]

        monkeypatch.setattr("apps.place.management.commands.embed_places.embed_texts", fake_embed_texts)

        call_command("embed_places", "--dry-run", "--settings=config.settings.local")

        assert PlaceFeature.objects.get(place=place).content_vector is None
