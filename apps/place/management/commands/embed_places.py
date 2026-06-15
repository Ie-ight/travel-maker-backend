"""장소 텍스트 임베딩(content_vector) 적재 management command (P1.5, §4).

provider 토글(ollama | gemini). ollama 기본 모델은 bge-m3(1024D, 로컬).
HNSW 인덱스(place_content_vector_hnsw)는 모델/마이그레이션에 이미 포함되어 있으나,
대량 적재 시에는 적재 완료 후 인덱스를 생성하는 편이 빌드 비용이 적다(§4.3 노트).

    docker compose ... exec web uv run python manage.py embed_places \
        --only-missing --batch-size 32 --settings=config.settings.local
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q

from apps.place.models import Place
from apps.place.services.embedding_service import (
    EmbeddingError,
    build_embedding_text,
    embed_texts,
    persist_content_vector,
)


class Command(BaseCommand):
    help = "장소의 제목/분류/설명을 1024D 텍스트 임베딩으로 변환해 PlaceFeature.content_vector에 저장한다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--content-type-id", type=int, default=None, help="특정 관광타입만(미지정 시 전체)")
        parser.add_argument("--only-missing", action="store_true", help="content_vector가 비어있는 장소만")
        parser.add_argument("--limit", type=int, default=None, help="처리할 최대 장소 수(미지정 시 전체)")
        parser.add_argument("--batch-size", type=int, default=32, help="배치당 인코딩 건수")
        parser.add_argument("--provider", choices=["ollama", "gemini"], default=None, help="미지정 시 settings 기본값")
        parser.add_argument("--model", default=None, help="모델 오버라이드(미지정 시 provider 기본값)")
        parser.add_argument("--dry-run", action="store_true", help="인코딩만 하고 DB 저장은 하지 않음")

    def handle(self, *args: Any, **options: Any) -> None:
        provider = (options["provider"] or settings.EMBEDDING_PROVIDER).lower()
        if provider == "gemini" and not settings.GEMINI_API_KEY:
            raise CommandError("GEMINI_API_KEY가 설정되지 않았습니다. envs/.env.local에 추가하세요.")

        # PlaceFeature가 없는 장소(예: description 없어 AI 태깅 보류)도 대상 — persist_content_vector가 새로 만든다
        queryset = Place.objects.filter(is_active=True)
        if options["content_type_id"] is not None:
            queryset = queryset.filter(content_type_id=options["content_type_id"])
        if options["only_missing"]:
            queryset = queryset.filter(Q(place_feature__isnull=True) | Q(place_feature__content_vector__isnull=True))
        queryset = queryset.order_by("id")
        if options["limit"] is not None:
            queryset = queryset[: options["limit"]]

        places = list(queryset)
        batch_size = options["batch_size"]
        model = options["model"]
        dry_run = options["dry_run"]

        processed = errors = 0
        for start in range(0, len(places), batch_size):
            batch = places[start : start + batch_size]
            texts = [build_embedding_text(place) for place in batch]
            try:
                vectors = embed_texts(texts, provider=provider, model=model)
            except EmbeddingError as exc:
                errors += len(batch)
                self.stderr.write(f"  배치({start}~{start + len(batch)}) 실패: {exc}")
                continue

            if not dry_run:
                for place, vector in zip(batch, vectors, strict=True):
                    persist_content_vector(place, vector)
            processed += len(batch)
            self.stdout.write(f"  처리: {processed}/{len(places)}")

        self.stdout.write(self.style.SUCCESS(f"임베딩 적재 완료 (provider={provider}{', dry-run' if dry_run else ''})"))
        self.stdout.write(f"  처리: {processed}")
        self.stdout.write(f"  실패: {errors}")
