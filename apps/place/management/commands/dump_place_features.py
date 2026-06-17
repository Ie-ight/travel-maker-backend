"""PlaceFeature를 content_id 기준 JSON으로 덤프한다(다른 환경 DB로 이전용).

place_id(PK)는 환경마다 다를 수 있어 Tour API 고유값인 content_id를 키로 담는다.
1024D content_vector가 포함돼 용량이 크므로(2만 건 기준 수백MB), --out 경로가
.gz로 끝나면 gzip으로 압축해 쓴다.

    docker compose ... exec web uv run python manage.py dump_place_features \
        --out place_features.json.gz --settings=config.settings.local
"""

import gzip
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.place.models import PlaceFeature
from apps.place.services.place_feature_dump_service import serialize_place_features


class Command(BaseCommand):
    help = "PlaceFeature를 content_id 기준 JSON으로 덤프한다(다른 환경 DB로 이전 시 사용)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--out", required=True, help="출력 JSON 경로(.gz로 끝나면 gzip 압축)")
        parser.add_argument("--limit", type=int, default=None, help="덤프할 최대 건수(미지정 시 전체)")

    def handle(self, *args: Any, **options: Any) -> None:
        queryset = PlaceFeature.objects.select_related("place").order_by("place_id")
        if options["limit"] is not None:
            queryset = queryset[: options["limit"]]

        rows = serialize_place_features(queryset)

        path = Path(options["out"])
        path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        if path.suffix == ".gz":
            with gzip.open(path, "wt", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    count += 1
        else:
            with path.open("wt", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    count += 1

        self.stdout.write(self.style.SUCCESS(f"덤프 완료: {count}건 → {options['out']}"))
