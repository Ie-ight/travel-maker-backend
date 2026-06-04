"""기존 수집분에 결정론 태그(지역·편의성)를 백필한다 (단계 4).

태그 시드가 먼저 적재돼 있어야 한다(`seed_tags`).

    docker compose ... exec web uv run python manage.py assign_tags --settings=config.settings.local
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.place.models import Place
from apps.place.services.tagging import assign_deterministic_tags


class Command(BaseCommand):
    help = "수집된 장소에 지역·편의성 태그를 (재)부여한다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--content-type-id", type=int, default=None, help="특정 관광타입만 처리(미지정 시 전체)")

    def handle(self, *args: Any, **options: Any) -> None:
        queryset = Place.objects.prefetch_related("tags").select_related("info")
        content_type_id = options["content_type_id"]
        if content_type_id is not None:
            queryset = queryset.filter(content_type_id=content_type_id)

        count = 0
        for place in queryset:
            assign_deterministic_tags(place)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"태그 부여 완료: {count}건"))
