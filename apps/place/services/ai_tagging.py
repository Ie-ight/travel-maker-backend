"""AI 태그 + style_vector 산출 (단계 5, §9 계약).

provider 토글(gemini | ollama)로 LLM이 overview 등을 입력받아 `여행 스타일`·`세부 테마`·`동행`
태그와 6차원 성향 벡터를 동시에 산출한다. 두 provider 모두 JSON 출력을 강제하고,
가드레일(후보 한정·벡터 6개·0~1)은 코드 검증으로 보장한다. 호출부만 분기하고 프롬프트·검증은 공유한다.
프롬프트 문구는 여기서 튜닝한다(§9 — 문서에는 박지 않음).
"""

import json
from dataclasses import dataclass
from typing import Any

import ollama
from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from apps.place.models import Place, PlaceFeature
from apps.place.services.lcls_codes import lcls_label
from apps.place.services.tag_seeds import (
    AI_TAG_TYPES,
    FESTIVAL_CONTENT_TYPE_ID,
    FOOD_CONTENT_TYPE_ID,
    FOOD_LCLS1_CODE,
    FOOD_TAG_NAMES,
    TAG_SEEDS,
)
from apps.place.services.tagging import assign_ai_tags

STYLE_VECTOR_DIM = 6


def content_type_label(content_type_id: int) -> str:
    """contenttypeid → 타입명 라벨(AI 입력 맥락·리포트용). enum에 없는 값은 코드 문자열로 폴백."""
    try:
        return Place.ContentType(content_type_id).label
    except ValueError:
        return str(content_type_id)


#: §4 6축 정의 (프롬프트용). 각 축은 양극단 + 앵커 예시로 폴라리티를 못 헷갈리게 한다.
_AXES = [
    "활동성: 1.0=액티비티형(많이 걷고 몸을 씀, 예: 등산·수상레저·테마파크) / "
    "0.0=힐링형(앉아 쉬고 여유, 예: 카페·온천·전망 감상)",
    "계획성: 1.0=계획형(예약·일정 필요, 예: 공연·전시·숙박) / 0.0=즉흥형(지나가다 들름, 예: 시장·거리·공원)",
    "사교성: 1.0=혼자형(혼자 즐기기 좋음, 예: 서점·미술관·산책로) / "
    "0.0=단체형(여럿이 어울림, 예: 축제·놀이공원·고깃집)",
    "공간지향: 1.0=자연형(산·바다·숲 등 한적한 야외, 예: 국립공원·해수욕장·사찰) / "
    "0.0=도시형(번화가·실내 상업시설, 예: 백화점·아울렛·도심 상가·쇼핑몰). "
    "도심 공원·녹지·하천변은 도심 속에서 자연을 즐기는 공간이라 도시형보다 자연형에 가깝다 — "
    "단 산·바다·숲 같은 한적한 자연만큼 높진 않다. 녹지·물·숲이 많을수록 더 자연 쪽으로, "
    "운동장·광장 등 시설 위주면 덜 자연 쪽으로 장소마다 다르게 매긴다. "
    "★주의: 건물이 크고 넓다고 높이지 말 것. '자연 속이면 높게, 도심·상권·실내면 낮게'가 기준이다.",
    "경험지향: 1.0=문화형(보고 감상, 예: 박물관·유적·전시) / 0.0=체험형(직접 참여·놀이, 예: 체험장·레포츠·테마파크)",
    "소비스타일: 1.0=가성비형(저렴·무료, 예: 공원·시장·무료시설) / "
    "0.0=럭셔리형(고가·프리미엄, 예: 특급호텔·고급 레스토랑)",
]

_CANDIDATES = "\n".join(f"- {ttype.label}: {', '.join(TAG_SEEDS[ttype])}" for ttype in AI_TAG_TYPES)

SYSTEM_PROMPT = (
    "너는 한국 여행지의 성향을 분석해 태그와 6차원 성향 벡터를 산출하는 분류기다. "
    "반드시 아래 JSON 형식으로만 응답한다.\n\n"
    "[태그 후보 — 이 목록의 값에서만 고른다. 새 태그 생성 금지]\n"
    f"{_CANDIDATES}\n"
    "[태그 규칙] 확실한 근거가 있는 것만 부여하고, 애매하면 넣지 않는다(과다 부여 금지).\n"
    "- `분류`는 한국관광공사 공식 카테고리다(예: '음식 > ...', '자연관광 > ...', '체험관광 > 웰니스관광 > 온천...'). "
    "이 분류로 장소의 본질을 먼저 판단한다.\n"
    "- 음식 계열(미식·음식점·카페·디저트·시장·먹거리)은 `분류`가 '음식'이거나 overview가 음식을 "
    "핵심으로 다룰 때만 부여한다. 온천·해수욕장·섬 등 음식이 아닌 분류에는 음식 태그를 넣지 않는다.\n"
    "- 동행은 분명히 어울리는 것만 고른다(무난하다고 4종을 다 넣지 말 것).\n"
    "- 여행 스타일의 해변·산악·도시는 장소의 입지(환경)를 뜻하며, 미식·문화 등 성격 태그와 함께 붙을 수 있다. "
    "overview·주소에서 바닷가·해안·해수욕장이면 해변, 산·숲·계곡이면 산악, 도심·번화가·상권이면 도시를 "
    "입지가 분명할 때 함께 부여한다(예: 바닷가 음식점 → 미식 + 해변).\n"
    "- 여행 스타일은 반드시 최소 1개 부여한다.\n"
    "- 지역·편의성 태그는 다루지 않는다.\n\n"
    "[style_vector — 정확히 6개 실수, 축 순서 고정]\n"
    "- 각 값은 0.000~1.000, **소수점 셋째 자리까지** 정밀하게 매긴다(예: 0.683, 0.412, 0.275). 0.500=중립.\n"
    "- 0.05·0.1 단위로 뭉뚱그리지 말고 실제 강도를 셋째 자리까지 반영한다.\n"
    + "\n".join(f"{i}. {axis}" for i, axis in enumerate(_AXES))
    + "\noverview가 비면 분류체계·타입으로 최소 추정하되, 근거가 약하면 중립(0.500)에 둔다.\n\n"
    "[강도 기준 예시 — 헷갈리는 축의 감각만 잡는 참고치다. 비슷하다고 그대로 복사하지 말고 장소에 맞게 조정한다]\n"
    "- 국립공원(등산·자연): [0.782, 0.314, 0.386, 0.843, 0.227, 0.458] — 직접 걷는 활동이자 체험이고 자연 속.\n"
    "- 분식·국수집(음식점): [0.214, 0.268, 0.437, 0.126, 0.183, 0.742] — 먹는 체험이고 도시 실내, 저렴.\n"
    "- 미술관·박물관(전시 감상): [0.183, 0.536, 0.718, 0.342, 0.857, 0.446] — 보고 감상하며 혼자 차분히.\n"
    "  (예시 숫자는 셋째 자리까지 — 너도 0.05·0.1로 뭉치지 말고 이렇게 세밀하게 매겨라)\n\n"
    "[reason 규칙] 태그·벡터를 그렇게 정한 핵심 근거만 한국어 한 문장(60자 이내)으로 쓴다. "
    "6개 축을 하나씩 나열하거나 숫자(0.3 등)를 되풀이하지 말고, "
    "장소의 본질(분류·overview 핵심)이 무엇이라 그렇게 판단했는지만 간결·명확히 적는다.\n\n"
    "[출력 JSON 형식]\n"
    '{"tags": {"여행 스타일": [...], "세부 테마": [...], "동행": [...]}, '
    '"style_vector": [0.182, 0.634, 0.771, 0.345, 0.792, 0.613], "reason": "핵심 근거 한 문장(60자 이내)"}'
)


class AITaggingError(Exception):
    """AI 분석 호출/파싱 실패."""


@dataclass
class AIResult:
    tags: dict[str, list[str]]  # tag_type → tag_name 목록 (후보로 필터됨)
    style_vector: list[float]  # 정확히 6개, [0, 1]
    reason: str


def _build_user_text(place: Place) -> str:
    type_name = content_type_label(place.content_type_id)
    # 원시 코드(VE/VE07/...) 대신 분류명("문화관광 > 전시시설 > 박물관")을 줘 모델이 음식/자연 등 범주를 직접 판단하게 한다
    lcls = lcls_label(place.lcls_systm1, place.lcls_systm2, place.lcls_systm3) or "-"
    return (
        f"장소명: {place.place_name}\n"
        f"타입: {type_name}\n"
        f"분류: {lcls}\n"
        f"주소: {place.address_primary or '-'}\n"
        f"설명(overview):\n{(place.description or '')[:1500] or '(없음)'}"
    )


def _clamp_vector(raw: Any) -> list[float]:
    """6개 실수로 정규화한다. [0,1] 클램프 + 소수점 둘째 자리 반올림(세밀하게 보존)."""
    if not isinstance(raw, list) or len(raw) != STYLE_VECTOR_DIM:
        raise AITaggingError(f"style_vector는 {STYLE_VECTOR_DIM}개 실수여야 함: {raw!r}")
    return [round(min(1.0, max(0.0, float(value))), 2) for value in raw]


def _filter_tags(raw: Any) -> dict[str, list[str]]:
    """후보 목록에 있는 태그만 남긴다(가드레일 #1)."""
    raw_tags = raw if isinstance(raw, dict) else {}
    result: dict[str, list[str]] = {}
    for ttype in AI_TAG_TYPES:
        candidates = set(TAG_SEEDS[ttype])
        names = raw_tags.get(ttype) or []
        result[ttype] = [name for name in dict.fromkeys(names) if name in candidates]
    return result


def _is_food_place(place: Place) -> bool:
    """공식 분류상 음식 장소인가(lclsSystm1=FD 또는 음식점 콘텐츠 타입)."""
    return place.lcls_systm1 == FOOD_LCLS1_CODE or place.content_type_id == FOOD_CONTENT_TYPE_ID


def _drop_non_food_tags(place: Place, tags: dict[str, list[str]]) -> dict[str, list[str]]:
    """음식 분류가 아닌 장소에서 음식 계열 태그를 제거한다.

    모델은 분류를 보여줘도 '간단한 식사 가능'·'주변 음식점' 등 주변부 근거로 미식·음식점을 과다부여한다.
    lclsSystm1이 음식(FD)을 비음식(자연·체험 등)과 깔끔히 분리하므로, 음식 장소가 아니면 결정론적으로 떼어낸다.

    단 축제(15)는 음식이 주제일 수 있고(김치·디저트·맥주 페스타) 모델이 음식/비음식 축제를 잘 구분하므로 제외한다.
    """
    if _is_food_place(place) or place.content_type_id == FESTIVAL_CONTENT_TYPE_ID:
        return tags
    return {ttype: [name for name in names if name not in FOOD_TAG_NAMES] for ttype, names in tags.items()}


#: 여행 스타일이 비었을 때 채울 폴백. content_type(타입이 성향을 강하게 규정) → lcls1 → 기본값 순.
_CT = Place.ContentType
_STYLE_BY_CTYPE: dict[int, str] = {
    _CT.FOOD: "미식",
    _CT.LEPORTS: "액티비티",
    _CT.CULTURE: "문화",
    _CT.FESTIVAL: "문화",
    _CT.SHOPPING: "도시",
    _CT.LODGING: "도시",
}
_LCLS = Place.LclsLarge
_STYLE_BY_LCLS1: dict[str, str] = {
    _LCLS.FOOD: "미식",
    _LCLS.EXPERIENCE: "액티비티",
    _LCLS.CULTURE: "문화",
    _LCLS.HISTORY: "문화",
}
_DEFAULT_STYLE = "도시"
#: 자연관광 중 해양 계열(해수욕장·섬 등) 중분류 접두 — 해변/산악 분기용(systm2는 enum화하지 않아 상수로 둔다).
_BEACH_LCLS2_PREFIX = "NA02"


def _fallback_style(place: Place) -> str:
    """여행 스타일 폴백 1개를 결정론으로 고른다(자연=해변/산악, 타입·분류 우선순위)."""
    if place.lcls_systm1 == _LCLS.NATURE:  # 자연관광: 해양이면 해변, 그 외(산·숲)는 산악
        return "해변" if (place.lcls_systm2 or "").startswith(_BEACH_LCLS2_PREFIX) else "산악"
    return (
        _STYLE_BY_CTYPE.get(place.content_type_id) or _STYLE_BY_LCLS1.get(place.lcls_systm1 or "", "") or _DEFAULT_STYLE
    )


def _ensure_min_style(place: Place, tags: dict[str, list[str]]) -> dict[str, list[str]]:
    """여행 스타일은 최소 1개 보장한다(모델 누락·필터로 비면 폴백)."""
    if not tags["여행 스타일"]:
        tags["여행 스타일"] = [_fallback_style(place)]
    return tags


def _gemini_generate(user_text: str, *, client: Any, model: str | None) -> str:
    """Gemini로 호출해 JSON 문자열을 반환한다."""
    api: Any = client if client is not None else genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = api.models.generate_content(
            model=model or settings.GEMINI_MODEL,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0,
                max_output_tokens=2048,
                # 분류 태스크라 추론 불필요 — thinking을 끄지 않으면 출력 예산을 소진해 JSON이 잘린다
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except genai_errors.APIError as exc:
        raise AITaggingError(f"Gemini 호출 실패: {exc}") from exc
    text = (response.text or "").strip()
    if not text:
        raise AITaggingError("Gemini 응답이 비어 있음(안전 차단 등 확인 필요)")
    return text


def _ollama_generate(user_text: str, *, client: Any, model: str | None) -> str:
    """로컬 Ollama(Gemma 등)로 호출해 JSON 문자열을 반환한다."""
    api: Any = client if client is not None else ollama.Client(host=settings.OLLAMA_HOST)
    try:
        response = api.chat(
            model=model or settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            format="json",  # 유효 JSON 강제
            options={"temperature": 0, "num_predict": 2048},
            think=False,  # Gemma 4 등 추론 모델의 thinking 차단하여 JSON 출력 예산 소진 방지
        )
    except Exception as exc:  # ollama 연결/추론 오류 일체
        raise AITaggingError(f"Ollama 호출 실패: {exc}") from exc
    message = response["message"] if isinstance(response, dict) else response.message
    content = (message["content"] if isinstance(message, dict) else message.content) or ""
    text = content.strip()
    if not text:
        raise AITaggingError("Ollama 응답이 비어 있음")
    return text


def analyze_place(
    place: Place, *, client: Any = None, model: str | None = None, provider: str | None = None
) -> AIResult | None:
    """장소를 AI로 분석한다(provider 토글). overview가 없으면 None(산출 보류, §9)."""
    if not (place.description or "").strip():
        return None

    provider = (provider or settings.AI_TAGGING_PROVIDER).lower()
    user_text = _build_user_text(place)
    if provider == "ollama":
        text = _ollama_generate(user_text, client=client, model=model)
    else:
        text = _gemini_generate(user_text, client=client, model=model)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AITaggingError(f"응답 JSON 파싱 실패: {text[:200]}") from exc

    return AIResult(
        tags=_ensure_min_style(place, _drop_non_food_tags(place, _filter_tags(data.get("tags")))),
        style_vector=_clamp_vector(data.get("style_vector")),
        reason=str(data.get("reason", "")),
    )


def persist_ai_result(place: Place, result: AIResult) -> None:
    """분석 결과를 DB에 반영한다(AI 태그 부여 + PlaceFeature 벡터 저장). 멱등."""
    names = [name for ttype in AI_TAG_TYPES for name in result.tags[ttype]]
    assign_ai_tags(place, names)
    PlaceFeature.objects.update_or_create(place=place, defaults={"style_vector": result.style_vector})


def tag_place_with_ai(
    place: Place, *, client: Any = None, model: str | None = None, provider: str | None = None
) -> bool:
    """장소에 AI 태그를 부여하고 style_vector를 PlaceFeature에 저장한다.

    overview가 없어 분석을 보류하면 False(태깅/벡터 미생성), 처리하면 True.
    """
    result = analyze_place(place, client=client, model=model, provider=provider)
    if result is None:
        return False

    persist_ai_result(place, result)
    return True
