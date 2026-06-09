"""여행 성향 유형(TravelType) 시드 적재.

TRAVEL_TYPE_SEEDS 정의로 TravelType을 idempotent하게 upsert한다. seed_tags 완료 후 실행한다.

    DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py seed_travel_types
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.travel_quiz.models import TravelType
from apps.travel_quiz.services.travel_type_seeds import TRAVEL_TYPE_SEEDS


class Command(BaseCommand):
    help = "여행 성향 유형(8종)을 시드 적재한다."

    def handle(self, *args: Any, **options: Any) -> None:
        created = updated = 0
        for type_key, data in TRAVEL_TYPE_SEEDS.items():
            _, is_created = TravelType.objects.update_or_create(type_key=type_key, defaults=data)
            if is_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS("여행 성향 유형 시드 완료"))
        self.stdout.write(f"  생성: {created}")
        self.stdout.write(f"  갱신: {updated}")
        self.stdout.write(f"  전체: {TravelType.objects.count()}")
