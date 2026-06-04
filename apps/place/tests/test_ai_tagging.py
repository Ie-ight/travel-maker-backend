"""AI 태깅(단계 5) 테스트 — 가짜 Gemini/Ollama 클라이언트 주입(실제 API 호출 없음)."""

import json
from typing import Any

import pytest
from django.core.management import call_command

from apps.place.models import Place, PlaceFeature
from apps.place.services.ai_tagging import (
    AITaggingError,
    analyze_place,
    tag_place_with_ai,
)


@pytest.fixture(autouse=True)
def _default_provider_gemini(settings: Any) -> None:
    # 기본 provider를 gemini로 고정 — env 토글(AI_TAGGING_PROVIDER)에 테스트가 휘둘리지 않게.
    # ollama 테스트는 provider="ollama"를 명시한다.
    settings.AI_TAGGING_PROVIDER = "gemini"


VALID_PAYLOAD: dict[str, Any] = {
    "tags": {
        "여행 스타일": ["문화", "로맨틱"],
        "세부 테마": ["박물관·전시"],
        "동행": ["혼자", "커플"],
    },
    "style_vector": [0.2, 0.65, 0.75, 0.35, 0.75, 0.65],
    "reason": "조용한 지역 서점, 감상·탐방 중심",
}


class _Models:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("Resp", (), {"text": self._text})()


class FakeClient:
    """analyze_place가 쓰는 models.generate_content만 흉내내는 가짜 Gemini 클라이언트."""

    def __init__(self, *, payload: Any = None, text: str | None = None) -> None:
        if text is None:
            text = json.dumps(payload)
        self.models = _Models(text)


class FakeOllamaClient:
    """analyze_place가 쓰는 chat()만 흉내내는 가짜 Ollama 클라이언트."""

    def __init__(self, *, payload: Any = None, text: str | None = None) -> None:
        self._text = json.dumps(payload) if text is None else text
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        message = type("Msg", (), {"content": self._text})()
        return type("Resp", (), {"message": message})()


def make_place(description: str = "가가책방은 공주시 최초의 동네 책방이다.", content_id: int = 1) -> Place:
    return Place.objects.create(
        place_name="가가책방",
        content_id=content_id,
        content_type_id=14,
        description=description,
        address_primary="충청남도 공주시",
        lcls_systm1="VE",
    )


def unsaved_place(description: str = "조용한 동네 책방") -> Place:
    return Place(place_name="가가책방", content_type_id=14, description=description, lcls_systm1="VE")


class TestAnalyzePlace:
    def test_정상_파싱(self) -> None:
        result = analyze_place(unsaved_place(), client=FakeClient(payload=VALID_PAYLOAD))
        assert result is not None
        assert result.tags["여행 스타일"] == ["문화", "로맨틱"]
        assert result.style_vector == [0.2, 0.65, 0.75, 0.35, 0.75, 0.65]
        assert result.reason

    def test_벡터_clamp(self) -> None:
        bad = {**VALID_PAYLOAD, "style_vector": [1.5, -0.2, 0.5, 0.5, 0.5, 0.5]}
        result = analyze_place(unsaved_place(), client=FakeClient(payload=bad))
        assert result is not None
        assert result.style_vector == [1.0, 0.0, 0.5, 0.5, 0.5, 0.5]

    def test_벡터_둘째자리_반올림(self) -> None:
        payload = {**VALID_PAYLOAD, "style_vector": [0.728, 0.382, 0.144, 0.5, 0.5, 0.5]}
        result = analyze_place(unsaved_place(), client=FakeClient(payload=payload))
        assert result is not None
        assert result.style_vector == [0.73, 0.38, 0.14, 0.5, 0.5, 0.5]

    def test_후보밖_태그_제거(self) -> None:
        bad = {**VALID_PAYLOAD, "tags": {"여행 스타일": ["문화", "없는태그"], "세부 테마": [], "동행": []}}
        result = analyze_place(unsaved_place(), client=FakeClient(payload=bad))
        assert result is not None
        assert result.tags["여행 스타일"] == ["문화"]

    def test_overview_없으면_None_이고_호출_안_함(self) -> None:
        client = FakeClient(payload=VALID_PAYLOAD)
        assert analyze_place(unsaved_place(description=""), client=client) is None
        assert client.models.calls == []  # API 미호출

    def test_벡터_6개_아니면_에러(self) -> None:
        bad = {**VALID_PAYLOAD, "style_vector": [0.1, 0.2, 0.3]}
        with pytest.raises(AITaggingError):
            analyze_place(unsaved_place(), client=FakeClient(payload=bad))

    def test_비_JSON_응답은_에러(self) -> None:
        with pytest.raises(AITaggingError):
            analyze_place(unsaved_place(), client=FakeClient(text="죄송하지만 JSON이 아닙니다"))

    def test_json모드_파라미터_전송(self) -> None:
        client = FakeClient(payload=VALID_PAYLOAD)
        analyze_place(unsaved_place(), client=client)
        config = client.models.calls[0]["config"]
        assert config.response_mime_type == "application/json"
        assert config.system_instruction and "후보" in config.system_instruction


@pytest.mark.django_db
class TestTagPlaceWithAI:
    @pytest.fixture(autouse=True)
    def _seed(self) -> None:
        call_command("seed_tags")

    def test_태그_부여_및_벡터_저장(self) -> None:
        place = make_place()
        assert tag_place_with_ai(place, client=FakeClient(payload=VALID_PAYLOAD)) is True
        assert set(place.tags.values_list("tag_name", flat=True)) == {"문화", "로맨틱", "박물관·전시", "혼자", "커플"}
        feature = PlaceFeature.objects.get(place=place)
        assert len(feature.style_vector) == 6
        assert float(feature.style_vector[0]) == pytest.approx(0.2, abs=1e-5)

    def test_overview_없으면_미생성(self) -> None:
        place = make_place(description="")
        assert tag_place_with_ai(place, client=FakeClient(payload=VALID_PAYLOAD)) is False
        assert PlaceFeature.objects.count() == 0

    def test_멱등_재실행(self) -> None:
        place = make_place()
        tag_place_with_ai(place, client=FakeClient(payload=VALID_PAYLOAD))
        updated = {**VALID_PAYLOAD, "style_vector": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]}
        tag_place_with_ai(place, client=FakeClient(payload=updated))
        assert PlaceFeature.objects.filter(place=place).count() == 1
        assert place.tags.filter(tag_type__in=["여행 스타일", "세부 테마", "동행"]).count() == 5
        assert float(PlaceFeature.objects.get(place=place).style_vector[1]) == pytest.approx(0.5, abs=1e-5)

    def test_결정론_태그_보존(self) -> None:
        from apps.place.models import Tag

        place = make_place()
        place.tags.add(Tag.objects.get(tag_name="충남"))  # 지역(결정론)
        tag_place_with_ai(place, client=FakeClient(payload=VALID_PAYLOAD))
        names = set(place.tags.values_list("tag_name", flat=True))
        assert "충남" in names and "문화" in names


FOOD_PAYLOAD: dict[str, Any] = {
    "tags": {
        "여행 스타일": ["미식", "해변"],
        "세부 테마": ["음식점", "카페·디저트", "해수욕·해안"],
        "동행": ["커플"],
    },
    "style_vector": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    "reason": "모델이 '식사 가능'으로 음식 태그를 붙인 경우",
}


def food_payload_place(*, content_type_id: int = 12, lcls_systm1: str = "NA") -> Place:
    """음식 태그가 섞인 응답을 받을, 분류만 다른 비저장 Place."""
    return Place(
        place_name="가계해수욕장",
        content_type_id=content_type_id,
        description="넓은 백사장과 다도해를 마주한 해수욕장. 스낵 코너에서 간단한 식사도 가능하다.",
        lcls_systm1=lcls_systm1,
    )


class TestNonFoodFilter:
    """음식 분류가 아닌 장소에서 음식 계열 태그(미식·음식점 등) 결정론적 제거."""

    def test_비음식_분류는_음식태그_제거(self) -> None:
        # 해수욕장(NA) — 미식·음식점·카페는 떼고 해변·해수욕·해안·커플은 보존
        result = analyze_place(food_payload_place(lcls_systm1="NA"), client=FakeClient(payload=FOOD_PAYLOAD))
        assert result is not None
        assert result.tags["여행 스타일"] == ["해변"]
        assert result.tags["세부 테마"] == ["해수욕·해안"]
        assert result.tags["동행"] == ["커플"]

    def test_음식_분류는_음식태그_보존(self) -> None:
        # lclsSystm1=FD(음식) — 그대로 둔다
        result = analyze_place(food_payload_place(lcls_systm1="FD"), client=FakeClient(payload=FOOD_PAYLOAD))
        assert result is not None
        assert result.tags["여행 스타일"] == ["미식", "해변"]
        assert result.tags["세부 테마"] == ["음식점", "카페·디저트", "해수욕·해안"]

    def test_음식점_콘텐츠타입은_보존(self) -> None:
        # contenttypeid=39(음식점) — lcls가 음식이 아니어도 음식 장소로 본다
        place = food_payload_place(content_type_id=39, lcls_systm1="")
        result = analyze_place(place, client=FakeClient(payload=FOOD_PAYLOAD))
        assert result is not None
        assert "미식" in result.tags["여행 스타일"]
        assert "음식점" in result.tags["세부 테마"]

    def test_분류없는_비음식점도_제거(self) -> None:
        # lcls 없음 + 음식점(39) 아님 → 음식 근거 없음 → 제거
        place = food_payload_place(content_type_id=12, lcls_systm1="")
        result = analyze_place(place, client=FakeClient(payload=FOOD_PAYLOAD))
        assert result is not None
        assert "미식" not in result.tags["여행 스타일"]
        assert "음식점" not in result.tags["세부 테마"]

    def test_축제는_음식태그_보존(self) -> None:
        # 축제(15)는 음식 축제(김치페스타 등)가 있어 필터 제외 → 모델의 미식 유지
        place = food_payload_place(content_type_id=15, lcls_systm1="EV")
        result = analyze_place(place, client=FakeClient(payload=FOOD_PAYLOAD))
        assert result is not None
        assert "미식" in result.tags["여행 스타일"]


class TestMinStyle:
    """여행 스타일 최소 1개 보장(모델 누락·필터로 비면 결정론 폴백)."""

    def _payload_no_style(self) -> dict[str, Any]:
        return {**VALID_PAYLOAD, "tags": {"여행 스타일": [], "세부 테마": ["랜드마크"], "동행": ["커플"]}}

    def test_빈_스타일은_폴백_부여(self) -> None:
        # 레포츠(28) → 액티비티
        place = Place(place_name="캠핑장", content_type_id=28, description="캠핑", lcls_systm1="AC", lcls_systm2="AC05")
        result = analyze_place(place, client=FakeClient(payload=self._payload_no_style()))
        assert result is not None
        assert result.tags["여행 스타일"] == ["액티비티"]

    def test_자연_해양은_해변_그외는_산악(self) -> None:
        payload = self._payload_no_style()
        beach = Place(place_name="해변", content_type_id=12, description="x", lcls_systm1="NA", lcls_systm2="NA02")
        mountain = Place(place_name="숲", content_type_id=12, description="x", lcls_systm1="NA", lcls_systm2="NA01")
        assert analyze_place(beach, client=FakeClient(payload=payload)).tags["여행 스타일"] == ["해변"]  # type: ignore[union-attr]
        assert analyze_place(mountain, client=FakeClient(payload=payload)).tags["여행 스타일"] == ["산악"]  # type: ignore[union-attr]

    def test_미식만_있다_필터되면_폴백(self) -> None:
        # 비음식(NA) 장소가 미식만 받음 → 미식 제거 → 폴백(해변)
        payload = {**VALID_PAYLOAD, "tags": {"여행 스타일": ["미식"], "세부 테마": [], "동행": []}}
        place = Place(place_name="섬", content_type_id=12, description="x", lcls_systm1="NA", lcls_systm2="NA02")
        result = analyze_place(place, client=FakeClient(payload=payload))
        assert result is not None
        assert result.tags["여행 스타일"] == ["해변"]


class TestRenderMarkdown:
    """ai_tag --out 의 Markdown 표 렌더러(부수효과 없는 순수 함수)."""

    def _rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": 12,
                "name": "가계해수욕장",
                "type": "관광지",
                "lcls": "자연관광 > 해변. 해수욕장",
                "tags": {"여행 스타일": ["해변"], "세부 테마": ["해수욕·해안"], "동행": ["커플", "가족"]},
                "vector": [0.5, 0.42, 0.3, 0.9, 0.1, 0.6],
                "reason": "해수욕장 본질",
            }
        ]

    def test_표_구조와_값(self) -> None:
        from apps.place.management.commands.ai_tag import render_markdown

        md = render_markdown(self._rows(), provider="ollama", model="gemma3:12b")
        assert "| id | 장소 |" in md  # 헤더
        assert "`ollama`" in md and "`gemma3:12b`" in md
        assert "| 12 | 가계해수욕장 | 관광지 |" in md
        assert "해수욕·해안" in md
        assert "커플, 가족" in md
        assert "0.50, 0.42, 0.30, 0.90, 0.10, 0.60" in md  # 둘째자리 고정

    def test_파이프_이스케이프(self) -> None:
        from apps.place.management.commands.ai_tag import render_markdown

        rows = self._rows()
        rows[0]["reason"] = "맛집|카페 인근"  # 파이프 포함
        md = render_markdown(rows, provider="ollama", model=None)
        assert "맛집\\|카페" in md  # 표가 깨지지 않게 이스케이프
        assert "model:" not in md  # model 미지정 시 생략

    def test_빈_태그는_하이픈(self) -> None:
        from apps.place.management.commands.ai_tag import render_markdown

        rows = self._rows()
        rows[0]["tags"] = {"여행 스타일": [], "세부 테마": [], "동행": []}
        md = render_markdown(rows, provider="gemini", model=None)
        assert "| - | - | - |" in md


class TestOllamaProvider:
    """provider="ollama" 분기 — 같은 검증·프롬프트를 공유하고 호출부만 다르다."""

    def test_정상_파싱(self) -> None:
        result = analyze_place(unsaved_place(), client=FakeOllamaClient(payload=VALID_PAYLOAD), provider="ollama")
        assert result is not None
        assert result.tags["여행 스타일"] == ["문화", "로맨틱"]
        assert result.style_vector == [0.2, 0.65, 0.75, 0.35, 0.75, 0.65]

    def test_format_json_과_system_전송(self) -> None:
        client = FakeOllamaClient(payload=VALID_PAYLOAD)
        analyze_place(unsaved_place(), client=client, provider="ollama")
        kwargs = client.calls[0]
        assert kwargs["format"] == "json"
        assert kwargs["messages"][0]["role"] == "system"
        assert "후보" in kwargs["messages"][0]["content"]

    def test_비_JSON_응답은_에러(self) -> None:
        with pytest.raises(AITaggingError):
            analyze_place(unsaved_place(), client=FakeOllamaClient(text="JSON 아님"), provider="ollama")

    @pytest.mark.django_db
    def test_tag_place_저장(self) -> None:
        call_command("seed_tags")
        place = make_place()
        assert tag_place_with_ai(place, client=FakeOllamaClient(payload=VALID_PAYLOAD), provider="ollama") is True
        assert PlaceFeature.objects.filter(place=place).exists()
        assert "문화" in set(place.tags.values_list("tag_name", flat=True))
