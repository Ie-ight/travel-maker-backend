"""기존 장소 detailIntro2 백필 — tel(infocenter*) + 누락 PlaceInfo를 한 호출로 채운다(멱등·재개).

tel이 빈 장소(축제 등 detailIntro2 미지원 타입 제외)만 detailIntro2를 재호출해 tel을 채우고,
PlaceInfo가 없으면 같은 응답으로 생성한다(신규 수집 없음). 모든 API 키 한도가 소진되면 거기까지
저장하고 중단하므로, 한도 회복 후 다시 실행하면 남은 건부터 이어간다.

    docker compose ... exec web uv run python manage.py backfill_details \
        --limit 100 --settings=config.settings.local
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.place.services.place_sync import backfill_details
from apps.place.services.tour_api import TourApiError


class Command(BaseCommand):
    help = "tel이 빈 기존 장소를 detailIntro2로 백필한다(tel + 누락 PlaceInfo, 신규 수집 없음, 멱등·재개)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--content-type-id", type=int, default=None, help="특정 관광타입만(미지정 시 전체)")
        parser.add_argument("--limit", type=int, default=None, help="처리할 최대 장소 수(미지정 시 전체)")
        parser.add_argument("--dry-run", action="store_true", help="조회만 하고 DB 저장은 하지 않음")
        parser.add_argument(
            "--refresh-info", action="store_true", help="누락 PlaceInfo 생성에 더해 기존 PlaceInfo도 새 intro로 갱신"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            summary = backfill_details(
                content_type_id=options["content_type_id"],
                limit=options["limit"],
                dry_run=options["dry_run"],
                refresh_info=options["refresh_info"],
            )
        except TourApiError as exc:
            raise CommandError(str(exc)) from exc

        mode = " (dry-run)" if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"detailIntro2 백필 완료{mode}"))
        self.stdout.write(f"  대상(빈 tel): {summary.target}")
        self.stdout.write(f"  처리(호출 성공): {summary.processed}")
        self.stdout.write(f"  tel 채움: {summary.tel_updated}")
        self.stdout.write(f"  tel 없음(infocenter 비어 있음): {summary.tel_missing}")
        self.stdout.write(f"  PlaceInfo 생성: {summary.info_created}")
        if options["refresh_info"]:
            self.stdout.write(f"  PlaceInfo 갱신: {summary.info_refreshed}")
        self.stdout.write(f"  호출 실패(다음 실행 재시도): {summary.errors}")
        if summary.aborted:
            self.stdout.write(
                self.style.WARNING("  ⚠ 모든 API 키 한도 소진으로 중단됨 — 한도 회복 후 다시 실행하면 이어집니다.")
            )
