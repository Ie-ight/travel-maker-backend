"""행동 기반 유저 콘텐츠 벡터 갱신 Celery 태스크 (§6.2/§6.3).

실시간 증분(update_user_content_vector_incremental)과 야간 배치 재계산
(recompute_user_content_vectors_batch) 두 경로로 UserPreference.content_vector를 갱신한다.
"""

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.user.models import UserActionLog, UserPreference
from apps.user.services import behavior_constants
from apps.user.services.user_content_vector_service import (
    apply_incremental_update,
    compute_user_content_vector_for_user,
    should_be_s3,
)

logger = logging.getLogger("user.content_vector")


@shared_task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)  # type: ignore[misc]
def update_user_content_vector_incremental(self, user_id: int, log_id: int) -> None:  # type: ignore[no-untyped-def]
    """행동 로그 1건 생성 직후 호출되는 실시간 증분 갱신 (§6.2)."""
    try:
        with transaction.atomic():
            try:
                log = UserActionLog.objects.select_related("place__place_feature").get(id=log_id, processed=False)
            except UserActionLog.DoesNotExist:
                return

            preference, _ = UserPreference.objects.select_for_update().get_or_create(user_id=user_id)
            preference.action_count += 1

            if should_be_s3(preference.action_count):
                place_feature = getattr(log.place, "place_feature", None)
                place_content_vector = getattr(place_feature, "content_vector", None) if place_feature else None
                if place_content_vector is not None:
                    new_vector = apply_incremental_update(
                        preference.content_vector, log.weight, list(place_content_vector)
                    )
                    preference.content_vector = new_vector

            preference.save(update_fields=["content_vector", "action_count", "updated_at"])

            log.processed = True
            log.save(update_fields=["processed"])
    except Exception as exc:
        raise self.retry(exc=exc) from exc


@shared_task(ignore_result=True)  # type: ignore[misc]
def recompute_user_content_vectors_batch() -> None:
    """야간 배치(§6.3): action_count >= S3_ACTION_COUNT_THRESHOLD인 유저의 content_vector 전체 재계산."""
    now = timezone.now()
    queryset = UserPreference.objects.filter(
        action_count__gte=behavior_constants.S3_ACTION_COUNT_THRESHOLD
    ).select_related("user")

    updated = skipped = 0
    for preference in queryset:
        vector = compute_user_content_vector_for_user(preference.user, apply_decay=True, now=now)
        preference.content_vector = vector
        preference.save(update_fields=["content_vector", "updated_at"])
        if vector is None:
            skipped += 1
        else:
            updated += 1

    logger.info("유저 콘텐츠 벡터 배치 재계산 완료: 갱신 %d, 영벡터(미생성) %d", updated, skipped)
