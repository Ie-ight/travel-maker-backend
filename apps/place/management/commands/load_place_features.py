"""dump_place_features로 만든 JSON을 content_id 기준으로 매칭해 PlaceFeature에 적재한다.

place_id(PK)는 환경마다 다를 수 있어 Tour API 고유값인 content_id로 Place를 찾는다.
content_id가 대상 DB에 없는 행은 건너뛴다(unmatched로 집계).
--in 경로가 .gz로 끝나면 gzip 압축 파일로 읽는다.

    docker compose ... exec web uv run python manage.py load_place_features \
        --in place_features.json.gz --settings=config.settings.local
"""

import gzip
import json
from pathlib import Path
from typing import Any, cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.place.services.place_feature_dump_service import PlaceFeatureRow, load_place_features


class Command(BaseCommand):
    help = "dump_place_features로 만든 JSON을 content_id 기준으로 매칭해 PlaceFeature에 적재한다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--in", dest="in_path", required=True, help="입력 JSON 경로(.gz면 gzip 압축 해제)")

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["in_path"])
        if not path.exists():
            raise CommandError(f"파일을 찾을 수 없습니다: {path}")

        from collections.abc import Iterator

        def _read_jsonl() -> Iterator[PlaceFeatureRow]:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            yield cast(PlaceFeatureRow, json.loads(line))
            else:
                with path.open("rt", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            yield cast(PlaceFeatureRow, json.loads(line))

        summary = load_place_features(_read_jsonl())

        self.stdout.write(self.style.SUCCESS("적재 완료"))
        self.stdout.write(f"  매칭: {summary.matched}")
        self.stdout.write(f"  미매칭(content_id 없음): {summary.unmatched}")
