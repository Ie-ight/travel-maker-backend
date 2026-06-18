from collections.abc import Sequence
from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.db import models
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe
from pgvector.django.vector import VectorWidget

# 권한은 User.role로 처리하므로 Django 기본 Group(= "인증 및 권한" 섹션)은 메뉴에서 숨긴다.
if admin.site.is_registered(Group):
    admin.site.unregister(Group)

# 성향 6축 라벨 (place.style_vector / user 성향 벡터 공통)
STYLE_AXIS_LABELS: tuple[str, ...] = ("활동성", "계획성", "사교성", "공간지향", "경험지향", "소비스타일")
_VECTOR_FIELD_HELP = (
    "6개 실수(0~1), 순서: 활동성·계획성·사교성·공간지향·경험지향·소비스타일. 예: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]"
)


# 사이드바 앱 표시 순서 (먼저 나올수록 위, 목록에 없는 앱은 뒤에 알파벳순)
_APP_ORDER = ["place", "route", "user"]
# 앱 내부 모델 순서 (object_name 기준, 미지정 모델은 뒤로)
_MODEL_ORDER: dict[str, list[str]] = {
    "place": ["Place", "Tag"],
    "route": ["Route", "RouteLike"],
}

_orig_get_app_list = admin.site.get_app_list


def _ordered_get_app_list(request: Any, app_label: str | None = None) -> list[Any]:
    """기본 알파벳순 대신 _APP_ORDER·_MODEL_ORDER 기준으로 사이드바/대시보드 순서를 고정한다."""
    app_list = _orig_get_app_list(request, app_label)
    app_list.sort(key=lambda a: _APP_ORDER.index(a["app_label"]) if a["app_label"] in _APP_ORDER else 999)
    for app in app_list:
        order = _MODEL_ORDER.get(app["app_label"])
        if order:
            app["models"].sort(key=lambda m: order.index(m["object_name"]) if m["object_name"] in order else 999)
    return app_list


admin.site.get_app_list = _ordered_get_app_list  # type: ignore[method-assign]

admin.site.site_url = "https://www.travel-maker.site/"


class BaseAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_per_page = 20
    show_full_result_count = False
    ordering = ["-id"]
    empty_value_display = "—"


def render_thumbnail(url: str | None, size: int = 60) -> SafeString | str:
    """이미지 URL을 정사각 썸네일 <img>로 렌더링한다. URL이 없으면 빈 문자열."""
    if not url:
        return ""
    return format_html(
        '<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:4px;" loading="lazy" />',
        url,
        size,
        size,
    )


def format_style_vector(vector: Sequence[float] | None) -> str:
    """성향 6축 벡터를 라벨과 함께 읽기 쉬운 문자열로 만든다. 예: '활동성 0.92 · 계획성 0.31 …'."""
    if vector is None:
        return "—"
    return " · ".join(f"{label} {float(value):.2f}" for label, value in zip(STYLE_AXIS_LABELS, vector, strict=False))


class RoundedVectorWidget(VectorWidget):  # type: ignore[misc]
    """벡터 편집 입력창에 float32 꼬리(0.38999998…) 대신 소수 2자리로 보여준다. 저장값은 그대로 float32."""

    def format_value(self, value: Any) -> str | None:
        if hasattr(value, "tolist"):  # numpy 배열 → 파이썬 리스트
            value = value.tolist()
        if isinstance(value, list | tuple):
            value = [round(float(x), 2) for x in value]
        return super().format_value(value)  # type: ignore[no-any-return]


def apply_vector_widget(formfield: forms.Field | None, db_field_name: str, target: str) -> forms.Field | None:
    """admin의 formfield_for_dbfield에서 지정한 벡터 필드에 반올림·넓은 입력 위젯 + 도움말을 적용한다."""
    if db_field_name == target and formfield is not None:
        formfield.help_text = _VECTOR_FIELD_HELP
        # 고정폭 대신 컬럼에 맞춰 늘어나게(최대 40em)
        attrs = {**formfield.widget.attrs, "style": "width: 100%; max-width: 40em;"}
        formfield.widget = RoundedVectorWidget(attrs=attrs)
    return formfield


class SmallTextFieldMixIn:
    """기본적으로 텍스트필드(TextField)의 세로 길이를 2줄(rows=2)로 줄여서 어드민 UI를 깔끔하게 유지합니다.
    크게 보여야 하는 필드명은 `large_text_fields = ["description"]` 처럼 선언해 예외 처리할 수 있습니다.
    """

    large_text_fields: Sequence[str] = ()

    def formfield_for_dbfield(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> forms.Field | None:
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)  # type: ignore[misc]
        if isinstance(db_field, models.TextField) and formfield is not None:
            if db_field.name not in self.large_text_fields:
                formfield.widget.attrs.update({"rows": 2, "cols": 80})
            else:
                formfield.widget.attrs.update({"rows": 10, "cols": 80})
        return formfield


class VectorChartMixIn:
    """장소, 유저 등 성향 벡터(6축)를 가진 모델에서 레이더 차트를 렌더링하는 공통 믹스인"""

    def get_vector_data(self, obj) -> list[float] | None:
        """모델별로 다른 벡터 필드명(style_vector, result_vector 등)을 찾아 반환"""
        if hasattr(obj, "style_vector") and obj.style_vector is not None:
            return [float(x) for x in obj.style_vector]
        if hasattr(obj, "result_vector") and obj.result_vector is not None:
            return [float(x) for x in obj.result_vector]
        return None

    @admin.display(description="현재 성향 차트")
    def vector_chart(self, obj):
        vector_data = self.get_vector_data(obj) or [0, 0, 0, 0, 0, 0]

        return mark_safe(f"""
            <div style="display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-start; margin-top: 10px;">
                <div style="width: 400px; height: 400px; background: transparent; padding: 20px; border-radius: 8px;">
                    <canvas id="vectorRadarChart" data-vector="{vector_data}"></canvas>
                </div>
                <div style="padding: 20px; background: var(--darkened-bg, var(--body-bg)); border-radius: 8px; font-size: 13px; color: var(--body-fg); min-width: 300px; border: 1px solid var(--border-color); box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    <h4 style="margin-top: 0; color: var(--body-fg); font-weight: bold; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 15px; font-size: 14px;">
                        🧭 성향 지표 해석 가이드
                    </h4>
                    <ul style="list-style: none; padding: 0; margin: 0; line-height: 2.2;">
                        <li><b>🏃 활동성:</b> <span style="color:#818cf8; font-weight:bold;">100% 액티비티형</span> <span style="color:var(--body-quiet-color); margin:0 5px;">↔</span> <span style="color:#fb7185; font-weight:bold;">0% 힐링·휴식형</span></li>
                        <li><b>📅 계획성:</b> <span style="color:#818cf8; font-weight:bold;">100% 철저한 계획형</span> <span style="color:var(--body-quiet-color); margin:0 5px;">↔</span> <span style="color:#fb7185; font-weight:bold;">0% 즉흥·발길 닿는 대로</span></li>
                        <li><b>🤝 사교성:</b> <span style="color:#818cf8; font-weight:bold;">100% 나홀로·독립형</span> <span style="color:var(--body-quiet-color); margin:0 5px;">↔</span> <span style="color:#fb7185; font-weight:bold;">0% 단체·어울림형</span></li>
                        <li><b>🌲 공간지향:</b> <span style="color:#818cf8; font-weight:bold;">100% 대자연·한적함</span> <span style="color:var(--body-quiet-color); margin:0 5px;">↔</span> <span style="color:#fb7185; font-weight:bold;">0% 화려한 도심형</span></li>
                        <li><b>🖼️ 경험지향:</b> <span style="color:#818cf8; font-weight:bold;">100% 관람·문화감상</span> <span style="color:var(--body-quiet-color); margin:0 5px;">↔</span> <span style="color:#fb7185; font-weight:bold;">0% 직접 체험·액션형</span></li>
                        <li><b>💸 소비지향:</b> <span style="color:#818cf8; font-weight:bold;">100% 알뜰·가성비형</span> <span style="color:var(--body-quiet-color); margin:0 5px;">↔</span> <span style="color:#fb7185; font-weight:bold;">0% 프리미엄·럭셔리형</span></li>
                    </ul>
                </div>
            </div>
        """)

    @property
    def media(self):
        base_media = super().media if hasattr(super(), "media") else forms.Media()
        chart_media = forms.Media(
            js=[
                "https://cdn.jsdelivr.net/npm/chart.js",
                "vector_chart.js",
            ]
        )
        return base_media + chart_media


class RangeSliderWidget(forms.NumberInput):
    input_type = "range"

    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        # 슬라이더를 움직일 때 바로 옆에 있는 span의 텍스트를 실시간으로 업데이트
        attrs["oninput"] = 'this.nextElementSibling.innerText = this.value + "%";'
        attrs["style"] = "margin-right: 10px; cursor: pointer; vertical-align: middle;"

        input_html = super().render(name, value, attrs, renderer)
        display_value = value if value is not None else 50
        # 인풋 태그와 실시간 수치(span)를 나란히 배치
        return mark_safe(
            f'<div style="display: inline-flex; align-items: center;">{input_html}<span style="font-weight: bold; min-width: 45px; color: #818cf8;">{display_value}%</span></div>'
        )


class VectorEditFormMixIn(forms.ModelForm):  # type: ignore[type-arg]
    """0~100% 형태의 슬라이더 바를 이용해 직관적으로 벡터값을 조작하는 커스텀 폼 공통 부모"""

    v1_activity = forms.FloatField(
        label="🏃 활동성 (힐링 ↔ 액티비티)",
        widget=RangeSliderWidget(attrs={"min": "0", "max": "100", "step": "1"}),
        required=False,
    )
    v2_plan = forms.FloatField(
        label="📅 계획성 (즉흥 ↔ 계획)",
        widget=RangeSliderWidget(attrs={"min": "0", "max": "100", "step": "1"}),
        required=False,
    )
    v3_social = forms.FloatField(
        label="🤝 사교성 (단체 ↔ 나홀로)",
        widget=RangeSliderWidget(attrs={"min": "0", "max": "100", "step": "1"}),
        required=False,
    )
    v4_nature = forms.FloatField(
        label="🌲 공간지향 (도심 ↔ 자연)",
        widget=RangeSliderWidget(attrs={"min": "0", "max": "100", "step": "1"}),
        required=False,
    )
    v5_culture = forms.FloatField(
        label="🖼️ 경험지향 (체험 ↔ 문화)",
        widget=RangeSliderWidget(attrs={"min": "0", "max": "100", "step": "1"}),
        required=False,
    )
    v6_cost = forms.FloatField(
        label="💸 소비지향 (럭셔리 ↔ 가성비)",
        widget=RangeSliderWidget(attrs={"min": "0", "max": "100", "step": "1"}),
        required=False,
    )

    def get_vector_field_name(self) -> str:
        """자식 클래스에서 오버라이드. (예: 'style_vector', 'result_vector')"""
        return "style_vector"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        field_name = self.get_vector_field_name()
        if self.instance and self.instance.pk and getattr(self.instance, field_name, None) is not None:
            vec = getattr(self.instance, field_name)
            if len(vec) >= 6:
                self.initial["v1_activity"] = int(float(vec[0]) * 100)
                self.initial["v2_plan"] = int(float(vec[1]) * 100)
                self.initial["v3_social"] = int(float(vec[2]) * 100)
                self.initial["v4_nature"] = int(float(vec[3]) * 100)
                self.initial["v5_culture"] = int(float(vec[4]) * 100)
                self.initial["v6_cost"] = int(float(vec[5]) * 100)
        else:
            for field in ["v1_activity", "v2_plan", "v3_social", "v4_nature", "v5_culture", "v6_cost"]:
                self.initial[field] = 50

    def save(self, commit: bool = True) -> Any:
        instance = super().save(commit=False)
        v1 = float(self.cleaned_data.get("v1_activity", 50)) / 100.0
        v2 = float(self.cleaned_data.get("v2_plan", 50)) / 100.0
        v3 = float(self.cleaned_data.get("v3_social", 50)) / 100.0
        v4 = float(self.cleaned_data.get("v4_nature", 50)) / 100.0
        v5 = float(self.cleaned_data.get("v5_culture", 50)) / 100.0
        v6 = float(self.cleaned_data.get("v6_cost", 50)) / 100.0

        field_name = self.get_vector_field_name()
        setattr(instance, field_name, [v1, v2, v3, v4, v5, v6])

        if commit:
            instance.save()
        return instance
