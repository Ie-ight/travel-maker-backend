from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.utils.safestring import SafeString

from apps.core.admin import BaseAdmin, render_thumbnail
from apps.travel_quiz.models import TravelType


@admin.register(TravelType)
class TravelTypeAdmin(BaseAdmin):
    list_display = ["id", "type_key", "name", "avatar", "user_count"]
    list_display_links = ["id", "type_key"]
    search_fields = ["type_key", "name"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[TravelType]:
        qs: QuerySet[TravelType] = super().get_queryset(request)
        return qs.annotate(user_count=Count("usertestresult", distinct=True))

    @admin.display(description="이미지")
    def avatar(self, obj: TravelType) -> SafeString | str:
        return render_thumbnail(obj.image_url, size=48)

    @admin.display(description="유저 수", ordering="user_count")
    def user_count(self, obj: TravelType) -> int:
        return int(getattr(obj, "user_count", 0) or 0)


# UserTestResult(유저 성향)는 User 상세 인라인에서 보고 편집하므로 독립 admin(메뉴 항목)은 두지 않는다.
