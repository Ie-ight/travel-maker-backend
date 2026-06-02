"""Tour API 소량 수집 management command (단계 2 검증용).

예) docker compose ... exec web uv run python manage.py sync_places \
        --content-type-id 14 --num-rows 5 --settings=config.settings.local
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.place.services.place_sync import sync_area
from apps.place.services.tour_api import TourApiError


class Command(BaseCommand):
    help = "한국관광공사 Tour API로 한 타입·(선택)한 지역의 장소를 소량 수집한다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--content-type-id", type=int, default=14, help="관광타입 ID (기본 14: 문화시설)")
        parser.add_argument(
            "--ldong-regn-cd", type=str, default=None, help="법정동 시도 코드(지역 필터). 미지정 시 전국"
        )
        parser.add_argument("--num-rows", type=int, default=10, help="페이지당 결과 수")
        parser.add_argument("--pages", type=int, default=1, help="조회할 페이지 수")
        parser.add_argument("--dry-run", action="store_true", help="목록만 조회하고 DB 저장은 하지 않음")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            summary = sync_area(
                options["content_type_id"],
                ldong_regn_cd=options["ldong_regn_cd"],
                num_of_rows=options["num_rows"],
                pages=options["pages"],
                dry_run=options["dry_run"],
            )
        except TourApiError as exc:
            raise CommandError(str(exc)) from exc

        mode = " (dry-run)" if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"수집 완료{mode}"))
        self.stdout.write(f"  조회: {summary.fetched}")
        self.stdout.write(f"  이미지 없어 스킵: {summary.skipped_no_image}")
        self.stdout.write(f"  생성: {summary.created}")
        self.stdout.write(f"  갱신: {summary.updated}")
        self.stdout.write(f"  이미지 저장: {summary.images_saved}")
        self.stdout.write(f"  운영정보 저장: {summary.info_saved}")
