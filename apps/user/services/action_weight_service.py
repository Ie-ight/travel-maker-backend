"""행동 신호 가중치 계산 (§6/§7).

UserActionLog.weight = compute_final_weight(...) 값을 그대로 저장하며,
P3의 1024D 센트로이드 계산(§6.1)에서 Wᵢ로 재사용된다.
"""

import math

from apps.place.models import Place
from apps.user.models import UserActionLog
from apps.user.services import behavior_constants

ActionType = UserActionLog.ActionType


def compute_explicit_weight(action_type: str, rating: int | None = None) -> float:
    """§6 명시적 행동 신호 가중치(A). 리뷰는 rating으로 분기한다."""
    if action_type == ActionType.REVIEW:
        if rating is None:
            raise ValueError("review action requires rating")
        return behavior_constants.REVIEW_WEIGHT_BY_RATING[rating]
    if action_type == ActionType.BOOKMARK:
        return behavior_constants.BOOKMARK_WEIGHT
    if action_type == ActionType.UNBOOKMARK:
        return behavior_constants.UNBOOKMARK_WEIGHT
    if action_type == ActionType.ROUTE_ADD:
        return behavior_constants.ROUTE_ADD_WEIGHT
    raise ValueError(f"unknown action_type: {action_type}")


def compute_popularity_factor(place: Place) -> float:
    """§7 인기도 보정 P = 1 / log10(review_count + bookmark_count + offset)."""
    bookmark_count = place.bookmarks.count()  # type: ignore[attr-defined]
    total = place.rating_count + bookmark_count + behavior_constants.POPULARITY_LOG_OFFSET
    return 1.0 / math.log10(total)


def compute_final_weight(action_type: str, place: Place, rating: int | None = None) -> float:
    """W = A x P."""
    a = compute_explicit_weight(action_type, rating=rating)
    p = compute_popularity_factor(place)
    return a * p
