"""AI 태그 + style_vector 산출 management command (단계 5).

provider 토글(gemini | ollama). gemini는 GEMINI_API_KEY 필요, ollama는 로컬 서버 필요.
`--out <경로>`를 주면 처리 결과를 Markdown 표로 저장한다(검토용).

    docker compose ... exec web uv run python manage.py ai_tag \
        --content-type-id 14 --limit 5 --provider ollama \
        --out reports/ai_tags.md --settings=config.settings.local
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q

from apps.place.models import Place
from apps.place.services.ai_tagging import (
    AIResult,
    AITaggingError,
    analyze_place,
    content_type_label,
    persist_ai_result,
)
from apps.place.services.lcls_codes import lcls_label

#: §4 6축 순서(벡터 헤더 범례용)
_VECTOR_AXES = "활동성·계획성·사교성·공간지향·경험지향·소비스타일"

#: 프롬프트 튜닝 회귀용 골든 샘플(타입·엣지케이스 대표 content_id 목록). sync 후 손으로 큐레이션.
_GOLDEN_SAMPLE_PATH = Path(__file__).resolve().parents[2] / "services" / "golden_sample.json"


def _load_golden_ids() -> list[int]:
    return cast(list[int], json.loads(_GOLDEN_SAMPLE_PATH.read_text(encoding="utf-8")))


def _md_cell(text: str) -> str:
    """Markdown 표 셀로 안전하게: 파이프/개행 이스케이프."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(rows: list[dict[str, Any]], *, provider: str, model: str | None) -> str:
    """처리 결과 행들을 Markdown 표 문서로 렌더링한다(검토용, 부수효과 없음)."""
    header = (
        f"# AI 태깅 결과\n\n"
        f"- 생성: {datetime.now():%Y-%m-%d %H:%M}\n"
        f"- provider: `{provider}`" + (f" / model: `{model}`" if model else "") + f"\n- 대상: {len(rows)}건\n"
        f"- 벡터 축 순서: {_VECTOR_AXES} (0.0~1.0)\n\n"
        "| id | 장소 | 타입 | 분류 | 여행 스타일 | 세부 테마 | 동행 | 벡터 | 근거 |\n"
        "|----|------|------|------|------------|----------|------|------|------|\n"
    )
    lines = []
    for row in rows:
        tags: dict[str, list[str]] = row["tags"]
        vector = ", ".join(f"{v:.2f}" for v in row["vector"])
        cells = [
            str(row["id"]),
            _md_cell(row["name"]),
            _md_cell(row["type"]),
            _md_cell(row["lcls"]),
            _md_cell(", ".join(tags.get("여행 스타일", [])) or "-"),
            _md_cell(", ".join(tags.get("세부 테마", [])) or "-"),
            _md_cell(", ".join(tags.get("동행", [])) or "-"),
            _md_cell(vector),
            _md_cell(row["reason"] or "-"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return header + "\n".join(lines) + "\n"


def _row(place: Place, result: AIResult) -> dict[str, Any]:
    return {
        "id": place.id,
        "name": place.place_name,
        "type": content_type_label(place.content_type_id),
        "lcls": lcls_label(place.lcls_systm1, place.lcls_systm2, place.lcls_systm3) or "-",
        "tags": result.tags,
        "vector": result.style_vector,
        "reason": result.reason,
    }


class Command(BaseCommand):
    help = "수집된 장소에 AI 태그(여행 스타일·세부 테마·동행)와 style_vector를 부여한다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--content-type-id", type=int, default=None, help="특정 관광타입만(미지정 시 전체)")
        parser.add_argument("--limit", type=int, default=10, help="처리할 최대 장소 수(비용 제어)")
        parser.add_argument("--only-missing", action="store_true", help="PlaceFeature 없는 장소만")
        parser.add_argument("--dry-run", action="store_true", help="분석만 하고 DB 저장은 하지 않음")
        parser.add_argument("--provider", choices=["gemini", "ollama"], default=None, help="미지정 시 settings 기본값")
        parser.add_argument("--model", default=None, help="모델 오버라이드(미지정 시 provider 기본값)")
        parser.add_argument("--out", default=None, help="결과를 Markdown 표로 저장할 경로(미지정 시 화면 출력만)")
        parser.add_argument(
            "--golden",
            action="store_true",
            help="골든 샘플(golden_sample.json)만 태깅 — 프롬프트 튜닝 회귀 확인용(타입·limit 무시)",
        )
        parser.add_argument(
            "--rpm",
            type=int,
            default=None,
            help="분당 최대 요청 수(미지정 시 gemini=8, ollama=0(무제한). 0=무제한)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=4,
            help="병렬 처리를 위한 스레드 수 (provider=ollama 및 rpm=0 일때만 활성, 기본 4)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        provider = (options["provider"] or settings.AI_TAGGING_PROVIDER).lower()
        if provider == "gemini" and not settings.GEMINI_API_KEY:
            raise CommandError("GEMINI_API_KEY가 설정되지 않았습니다. envs/.env.local에 추가하세요.")

        # overview(description)가 있고 활성(소프트삭제 아님)인 장소만 — 분석 보류·삭제 장소 호출을 아낀다
        queryset = Place.objects.filter(is_active=True).exclude(description__isnull=True).exclude(description="")
        if options["golden"]:
            # 골든 샘플은 고정 세트 — 타입·only-missing·limit 필터를 무시하고 전량 태깅
            queryset = queryset.filter(content_id__in=_load_golden_ids()).order_by("id")
        else:
            if options["content_type_id"] is not None:
                queryset = queryset.filter(content_type_id=options["content_type_id"])
            if options["only_missing"]:
                # PlaceFeature 자체가 없거나, 임베딩만 채워지고 style_vector가 비어있는(§4.3) 장소 모두 대상
                queryset = queryset.filter(Q(place_feature__isnull=True) | Q(place_feature__style_vector__isnull=True))
            queryset = queryset.order_by("id")[: options["limit"]]

        dry_run = options["dry_run"]
        model = options["model"]
        out = options["out"]
        # 로컬(ollama)은 레이트리밋이 없어 기본 무제한, 원격(gemini)은 8 RPM
        rpm = options["rpm"] if options["rpm"] is not None else (0 if provider == "ollama" else 8)
        min_interval = 60.0 / rpm if rpm > 0 else 0.0  # 시작-시작 간격(호출 시간 포함)
        last_started = 0.0

        rows: list[dict[str, Any]] = []
        processed = skipped = errors = 0

        workers = options["workers"]
        if workers > 1 and rpm == 0:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            from django.db import close_old_connections

            self.stdout.write(self.style.SUCCESS(f"병렬 처리 시작 (스레드 수: {workers})..."))

            def process_place(place: Place) -> tuple[Place, Any, str]:
                close_old_connections()
                try:
                    result = analyze_place(place, provider=provider, model=model)
                    if result is None:
                        return place, None, "skipped"
                    if not dry_run:
                        persist_ai_result(place, result)
                    return place, result, "success"
                except Exception as exc:
                    return place, exc, "error"
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=workers) as executor:
                place_list = list(queryset)
                futures = {executor.submit(process_place, place): place for place in place_list}
                for future in as_completed(futures):
                    place = futures[future]
                    try:
                        place, result, status = future.result()
                        if status == "success":
                            processed += 1
                            if dry_run:
                                self.stdout.write(
                                    f"  [{place.content_id}] {place.place_name}: vector={result.style_vector}"
                                )
                                self.stdout.write(f"      tags={result.tags}")
                            if out is not None:
                                rows.append(_row(place, result))
                        elif status == "skipped":
                            skipped += 1
                        else:
                            errors += 1
                            self.stderr.write(f"  [{place.content_id}] 실패: {result}")
                    except Exception as e:
                        errors += 1
                        self.stderr.write(f"  [{place.content_id}] 예상치 못한 에러: {e}")
        else:
            for place in queryset:
                if min_interval:
                    wait = min_interval - (time.monotonic() - last_started)
                    if last_started and wait > 0:
                        time.sleep(wait)
                last_started = time.monotonic()
                try:
                    result = analyze_place(place, provider=provider, model=model)
                except AITaggingError as exc:
                    errors += 1
                    self.stderr.write(f"  [{place.content_id}] 실패: {exc}")
                    continue
                if result is None:
                    skipped += 1
                    continue

                if not dry_run:
                    persist_ai_result(place, result)
                processed += 1
                if dry_run:
                    self.stdout.write(f"  [{place.content_id}] {place.place_name}: vector={result.style_vector}")
                    self.stdout.write(f"      tags={result.tags}")
                if out is not None:
                    rows.append(_row(place, result))

        if out is not None:
            path = Path(out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_markdown(rows, provider=provider, model=model), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"문서 저장 → {out} ({len(rows)}건)"))

        self.stdout.write(self.style.SUCCESS(f"AI 태깅 완료 (provider={provider}{', dry-run' if dry_run else ''})"))
        self.stdout.write(f"  처리: {processed}")
        self.stdout.write(f"  보류(overview 없음): {skipped}")
        self.stdout.write(f"  실패: {errors}")
