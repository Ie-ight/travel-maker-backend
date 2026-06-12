from collections.abc import Sequence
from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.utils.safestring import SafeString
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
