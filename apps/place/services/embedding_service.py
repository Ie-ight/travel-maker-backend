"""장소 텍스트 임베딩(content_vector) 산출 (P1.5, §4).

provider 토글(ollama | gemini)로 장소의 제목/분류/설명을 1024D 벡터로 변환한다.
ollama 기본 모델은 bge-m3(1024D, 로컬). gemini는 gemini-embedding-001을
output_dimensionality=1024로 호출해 차원을 맞춘다.
"""

from typing import Any

import ollama
from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from apps.place.models import Place, PlaceFeature
from apps.place.services.lcls_codes import lcls_label

EMBEDDING_DIM = 1024


class EmbeddingError(Exception):
    """임베딩 호출/응답 처리 중 발생한 오류."""


def build_embedding_text(place: Place) -> str:
    """제목/분류/설명으로 임베딩 입력 텍스트를 구성한다(§4.1). description 없어도 인코딩 가능."""
    lcls = lcls_label(place.lcls_systm1, place.lcls_systm2, place.lcls_systm3) or "-"
    lines = [f"제목: {place.place_name}", f"분류: {lcls}"]
    description = (place.description or "").strip()
    if description:
        lines.append(f"설명: {description[:1500]}")
    return "\n".join(lines)


def _ollama_embed(texts: list[str], *, client: Any, model: str | None) -> list[list[float]]:
    api: Any = client if client is not None else ollama.Client(host=settings.OLLAMA_HOST)
    try:
        response = api.embed(model=model or settings.OLLAMA_EMBED_MODEL, input=texts)
    except Exception as exc:  # ollama 연결/추론 오류 일체
        raise EmbeddingError(f"Ollama 임베딩 호출 실패: {exc}") from exc
    embeddings = response["embeddings"] if isinstance(response, dict) else response.embeddings
    return [list(vector) for vector in embeddings]


def _gemini_embed(texts: list[str], *, client: Any, model: str | None) -> list[list[float]]:
    api: Any = client if client is not None else genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = api.models.embed_content(
            model=model or settings.GEMINI_EMBED_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
    except genai_errors.APIError as exc:
        raise EmbeddingError(f"Gemini 임베딩 호출 실패: {exc}") from exc
    embeddings = response["embeddings"] if isinstance(response, dict) else response.embeddings
    return [list(item["values"] if isinstance(item, dict) else item.values) for item in embeddings]


def embed_texts(
    texts: list[str], *, client: Any = None, model: str | None = None, provider: str | None = None
) -> list[list[float]]:
    """텍스트 목록을 1024D 벡터 목록으로 변환한다(배치). 차원이 다르면 EmbeddingError."""
    if not texts:
        return []

    provider = (provider or settings.EMBEDDING_PROVIDER).lower()
    if provider == "ollama":
        vectors = _ollama_embed(texts, client=client, model=model)
    else:
        vectors = _gemini_embed(texts, client=client, model=model)

    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise EmbeddingError(f"임베딩 차원 불일치: 기대 {EMBEDDING_DIM}, 실제 {len(vector)}")
    return vectors


def embed_place(
    place: Place, *, client: Any = None, model: str | None = None, provider: str | None = None
) -> list[float]:
    """장소 하나를 1024D 벡터로 변환한다."""
    return embed_texts([build_embedding_text(place)], client=client, model=model, provider=provider)[0]


def persist_content_vector(place: Place, vector: list[float]) -> None:
    """PlaceFeature.content_vector를 갱신한다.

    PlaceFeature가 없는 장소(예: description 없어 AI 태깅이 보류된 장소)는
    style_vector=None인 PlaceFeature를 새로 만든다. AI 태깅이 나중에 수행되면
    persist_ai_result가 같은 행의 style_vector만 채운다.
    """
    PlaceFeature.objects.update_or_create(place=place, defaults={"content_vector": vector})
