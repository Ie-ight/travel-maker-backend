"""lclsSystmCode2 분류 코드→이름 매핑을 받아 JSON으로 저장한다 (§6).

분류 코드는 자주 안 바뀌므로 필요할 때 수동 실행한다. AI 태깅이 코드 대신 분류명을 쓰게 한다.

    docker compose ... exec web uv run python manage.py sync_lcls_codes --settings=config.settings.local
"""

import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.place.services.lcls_codes import LCLS_CODES_PATH, load_lcls_map
from apps.place.services.tour_api import TourApiClient, TourApiError


class Command(BaseCommand):
    help = "분류체계(lclsSystmCode2) 코드→이름 매핑을 받아 lcls_codes.json에 저장한다."

    def handle(self, *args: Any, **options: Any) -> None:
        client = TourApiClient()
        mapping: dict[str, str] = {}
        try:
            for lv1 in client.lcls_systm_code():
                c1 = lv1["code"]
                mapping[c1] = lv1["name"]
                for lv2 in client.lcls_systm_code(lcls_systm1=c1):
                    c2 = lv2["code"]
                    mapping[c2] = lv2["name"]
                    for lv3 in client.lcls_systm_code(lcls_systm1=c1, lcls_systm2=c2):
                        mapping[lv3["code"]] = lv3["name"]
        except TourApiError as exc:
            self.stderr.write(f"중단(부분 저장): {exc}")

        LCLS_CODES_PATH.write_text(json.dumps(mapping, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        load_lcls_map.cache_clear()  # 캐시 갱신
        self.stdout.write(self.style.SUCCESS(f"분류 코드 {len(mapping)}개 저장 → {LCLS_CODES_PATH.name}"))
