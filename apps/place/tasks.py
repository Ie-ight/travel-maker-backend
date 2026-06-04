"""Celery 태스크 — 단계 7 운영 스케줄(증분 동기화·AI 태깅).

config/settings/prod.py의 CELERY_BEAT_SCHEDULE에서 호출한다(로컬 dev는 스케줄 없음).
배포 환경엔 ollama가 없어 태깅은 Gemini만 가능하므로, 일일 한도(20)·분당 한도(4)로 미태깅 백로그를 소진한다.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.management import call_command

from apps.place.services.place_sync import sync_incremental

logger = logging.getLogger("place.sync")


@shared_task(ignore_result=True)  # type: ignore[misc]
def sync_incremental_task() -> None:
    """월 1회: areaBasedSyncList2로 변경분만 반영(신규·변경 수집, showflag=0 소프트삭제)."""
    summary = sync_incremental()
    logger.info(
        "증분 동기화 태스크 완료: 생성 %d·갱신 %d·미변경 %d·삭제 %d",
        summary.created,
        summary.updated,
        summary.skipped_unchanged,
        summary.deactivated,
    )


@shared_task(ignore_result=True)  # type: ignore[misc]
def ai_tag_missing_task() -> None:
    """일 1회: 미태깅 장소를 Gemini로 일 한도(20)·분당 한도(4)만큼 태깅(배포는 ollama 불가)."""
    call_command(
        "ai_tag",
        provider="gemini",
        limit=settings.AI_TAG_GEMINI_DAILY_LIMIT,
        rpm=settings.AI_TAG_GEMINI_RPM,
        only_missing=True,
    )
