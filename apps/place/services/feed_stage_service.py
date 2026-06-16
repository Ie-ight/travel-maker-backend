from typing import Literal

from apps.travel_quiz.models import UserTestResult
from apps.user.models import UserPreference
from apps.user.services import behavior_constants

Stage = Literal["S1", "S2", "S3"]


def determine_stage(user_id: int | None) -> Stage:
    """sort=recommend의 개인화 단계(S1/S2/S3)를 판정한다 (§7.1)."""
    if user_id is None:
        return "S1"

    preference = UserPreference.objects.filter(user_id=user_id).first()
    action_count = preference.action_count if preference else 0

    if (
        action_count >= behavior_constants.S3_ACTION_COUNT_THRESHOLD
        and preference is not None
        and preference.content_vector is not None
    ):
        return "S3"

    if UserTestResult.objects.filter(user_id=user_id).exists():
        return "S2"

    return "S1"
