"""Tour API 수집 management command.

- 소량 검증(단계 2): 한 타입·소량.
    docker compose ... exec web uv run python manage.py sync_places \
        --content-type-id 14 --num-rows 5 --settings=config.settings.local
- 대량 적재(단계 6): 전체 타입 전국 페이지네이션 + 재개(skip-existing 기본 ON).
    ... python manage.py sync_places --all --settings=config.settings.local
- 증분 동기화(단계 7): areaBasedSyncList2로 변경분만(신규·변경 수집, showflag=0 소프트삭제).
    ... python manage.py sync_places --sync --settings=config.settings.local
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.place.services.place_sync import sync_all, sync_area, sync_incremental
from apps.place.services.tour_api import TourApiError


class Command(BaseCommand):
    help = "한국관광공사 Tour API로 장소를 수집한다(소량 검증 / --all 대량 / --sync 증분)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--content-type-id", type=int, default=14, help="관광타입 ID (기본 14: 문화시설). --all 시 무시"
        )
        parser.add_argument(
            "--ldong-regn-cd", type=str, default=None, help="법정동 시도 코드(지역 필터). 미지정 시 전국"
        )
        parser.add_argument("--num-rows", type=int, default=None, help="페이지당 결과 수 (기본: 소량 10, --all 1000)")
        parser.add_argument("--pages", type=int, default=1, help="조회할 페이지 수 (소량 모드)")
        parser.add_argument("--all", action="store_true", help="전체 타입 전국 대량 적재(단계 6)")
        parser.add_argument("--sync", action="store_true", help="전체 타입 증분 동기화(단계 7, areaBasedSyncList2)")
        parser.add_argument(
            "--max-pages", type=int, default=None, help="--all/--sync 시 타입별 최대 페이지(미지정 시 끝까지)"
        )
        parser.add_argument(
            "--refresh", action="store_true", help="--all 시 기존 장소도 다시 수집(기본은 skip-existing으로 건너뜀)"
        )
        parser.add_argument("--dry-run", action="store_true", help="목록만 조회하고 DB 저장은 하지 않음")

    def handle(self, *args: Any, **options: Any) -> None:
        is_all = options["all"]
        is_sync = options["sync"]
        if is_all and is_sync:
            raise CommandError("--all과 --sync는 함께 쓸 수 없습니다.")
        num_rows = options["num_rows"]
        if num_rows is None:
            num_rows = 1000 if (is_all or is_sync) else 10
        try:
            if is_sync:
                summary = sync_incremental(
                    num_of_rows=num_rows, max_pages=options["max_pages"], dry_run=options["dry_run"]
                )
            elif is_all:
                summary = sync_all(
                    num_of_rows=num_rows,
                    max_pages=options["max_pages"],
                    skip_existing=not options["refresh"],
                    dry_run=options["dry_run"],
                )
            else:
                summary = sync_area(
                    options["content_type_id"],
                    ldong_regn_cd=options["ldong_regn_cd"],
                    num_of_rows=num_rows,
                    pages=options["pages"],
                    dry_run=options["dry_run"],
                )
        except TourApiError as exc:
            raise CommandError(str(exc)) from exc

        mode = " (dry-run)" if options["dry_run"] else ""
        label = " [증분]" if is_sync else (" [전체 타입]" if is_all else "")
        self.stdout.write(self.style.SUCCESS(f"수집 완료{mode}{label}"))
        self.stdout.write(f"  조회: {summary.fetched}")
        self.stdout.write(f"  이미지 없어 스킵: {summary.skipped_no_image}")
        self.stdout.write(f"  기존이라 스킵: {summary.skipped_existing}")
        self.stdout.write(f"  미변경 스킵: {summary.skipped_unchanged}")
        self.stdout.write(f"  생성: {summary.created}")
        self.stdout.write(f"  갱신: {summary.updated}")
        self.stdout.write(f"  비활성화(삭제): {summary.deactivated}")
        self.stdout.write(f"  이미지 저장: {summary.images_saved}")
        self.stdout.write(f"  운영정보 저장: {summary.info_saved}")
