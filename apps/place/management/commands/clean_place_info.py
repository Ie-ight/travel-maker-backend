"""기존 PlaceInfo 자유 텍스트 정제 백필 — <br> 등 HTML 마크업 제거·줄바꿈 정규화(멱등, API 호출 없음).

수집 시점 정제는 이후 수집분에만 적용되므로, 이미 저장된 운영시간·휴무일·입장료 등의 <br>·<a> 마크업은
이 명령으로 정리한다. 값이 실제 바뀐 행만 갱신하며, 다시 실행해도 안전하다(이미 깨끗하면 변경 0).

    docker compose ... exec web uv run python manage.py clean_place_info \
        --dry-run --settings=config.settings.local
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.place.services.place_sync import clean_existing_place_info


class Command(BaseCommand):
    help = "기존 PlaceInfo 텍스트의 HTML 마크업을 제거하고 줄바꿈을 정규화한다(멱등, 신규 수집 없음)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="변경 건수만 집계하고 DB 저장은 하지 않음")
        parser.add_argument("--batch-size", type=int, default=500, help="bulk_update 배치 크기(기본 500)")

    def handle(self, *args: Any, **options: Any) -> None:
        summary = clean_existing_place_info(dry_run=options["dry_run"], batch_size=options["batch_size"])

        mode = " (dry-run)" if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"PlaceInfo 텍스트 정제 완료{mode}"))
        self.stdout.write(f"  조회: {summary.scanned}")
        self.stdout.write(f"  변경 행: {summary.changed_rows}")
        self.stdout.write(f"  변경 필드: {summary.changed_fields}")
