"""유저 행동 기반 1024D 콘텐츠 벡터 산출 (§6.1, embedding_recommendation_plan.md §2).

content_vector = normalize( sum( W_i * decay_i * place.place_feature.content_vector_i ) )

- W_i: UserActionLog.weight (생성 시점에 action_weight_service로 계산되어 저장됨)
- decay_i: exp(-lambda * 경과일) (배치 재계산 시 적용, 실시간 증분에서는 1.0)
- place_feature.content_vector가 없는(미임베딩) 행동은 합산에서 제외한다.
- 합산 결과의 L2 norm이 ZERO_VECTOR_NORM_EPSILON 미만이면 None을 반환한다
  (영벡터 안전장치 — UserPreference.content_vector를 null로 유지해 S2로 강제 유지).
"""

import logging
import math
from collections.abc import Iterable
from datetime import datetime, timedelta

import numpy as np
from django.utils import timezone

from apps.user.models import User, UserActionLog
from apps.user.services import behavior_constants

logger = logging.getLogger("user.content_vector")


def should_be_s3(action_count: int) -> bool:
    return action_count >= behavior_constants.S3_ACTION_COUNT_THRESHOLD


def _decay(created_at: datetime, *, now: datetime, lam: float) -> float:
    days = (now - created_at).total_seconds() / 86400.0
    return math.exp(-lam * max(days, 0.0))


def compute_user_content_vector(
    logs: Iterable[UserActionLog],
    *,
    apply_decay: bool = True,
    now: datetime | None = None,
    lam: float = behavior_constants.DEFAULT_DECAY_LAMBDA,
) -> np.ndarray | None:
    """행동 로그 목록으로부터 정규화된 1024D 벡터를 계산한다. 합산 대상이 없으면 None."""
    now = now or timezone.now()

    total = np.zeros(1024, dtype=np.float64)
    skipped = 0
    used = 0

    for log in logs:
        place_feature = getattr(log.place, "place_feature", None)
        content_vector = getattr(place_feature, "content_vector", None) if place_feature else None
        if content_vector is None:
            skipped += 1
            continue

        weight = log.weight
        if apply_decay:
            weight *= _decay(log.created_at, now=now, lam=lam)

        total += weight * np.asarray(content_vector, dtype=np.float64)
        used += 1

    if skipped and (used + skipped):
        ratio = skipped / (used + skipped)
        if ratio > 0.5:
            logger.warning(
                "유저 콘텐츠 벡터 계산 중 content_vector 누락 비율 높음: %.0f%% (skipped=%d)", ratio * 100, skipped
            )

    norm = float(np.linalg.norm(total))
    if norm < behavior_constants.ZERO_VECTOR_NORM_EPSILON:
        return None

    return total / norm


def apply_incremental_update(
    current_vector: np.ndarray | list[float] | None,
    weight: float,
    place_content_vector: list[float],
) -> np.ndarray | None:
    """실시간 증분 경로(§6.2): 기존 content_vector에 W * place.content_vector를 가산 후 정규화.

    current_vector가 None이면 새로 생성한다. 결과 norm이 ZERO_VECTOR_NORM_EPSILON 미만이면 None.

    주의: current_vector는 이전 호출에서 이미 정규화된 단위 벡터이므로, 매 호출마다
    "정규화 후 가산"을 반복하면 과거 행동의 누적 가중치가 호출 횟수에 따라 점차
    희석된다(decay와는 별개의 효과). 이는 의도된 근사이며, 야간 배치
    (recompute_user_content_vectors_batch)가 BEHAVIOR_LOOKBACK_DAYS 내 전체 로그를
    decay 적용해 재계산함으로써 주기적으로 보정한다.
    """
    base = np.zeros(1024, dtype=np.float64) if current_vector is None else np.asarray(current_vector, dtype=np.float64)
    total = base + weight * np.asarray(place_content_vector, dtype=np.float64)

    norm = float(np.linalg.norm(total))
    if norm < behavior_constants.ZERO_VECTOR_NORM_EPSILON:
        return None

    return total / norm


def compute_user_content_vector_for_user(
    user: User, *, apply_decay: bool = True, now: datetime | None = None
) -> np.ndarray | None:
    """유저의 최근 행동 로그(BEHAVIOR_LOOKBACK_DAYS) 기준으로 벡터를 계산한다 (배치 경로용)."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=behavior_constants.BEHAVIOR_LOOKBACK_DAYS)
    logs = UserActionLog.objects.filter(user=user, created_at__gte=cutoff).select_related("place__place_feature")
    return compute_user_content_vector(logs, apply_decay=apply_decay, now=now)
