"""태그 분류 시드 적재 (단계 4, §8).

TAG_SEEDS 정의로 Tag를 idempotent하게 upsert한다. 볼륨 재생성 후 다시 실행하면 된다.

    docker compose ... exec web uv run python manage.py seed_tags --settings=config.settings.local
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.place.models import Tag
from apps.place.services.tag_seeds import TAG_SEEDS


class Command(BaseCommand):
    help = "태그 분류(여행 스타일·세부 테마·동행·지역·편의성)를 시드 적재한다."

    def handle(self, *args: Any, **options: Any) -> None:
        created = updated = 0
        for tag_type, names in TAG_SEEDS.items():
            for name in names:
                _, is_created = Tag.objects.update_or_create(tag_name=name, defaults={"tag_type": tag_type})
                if is_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS("태그 시드 완료"))
        self.stdout.write(f"  생성: {created}")
        self.stdout.write(f"  갱신: {updated}")
        self.stdout.write(f"  전체: {Tag.objects.count()}")
