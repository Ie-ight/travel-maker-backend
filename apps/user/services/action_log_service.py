"""행동 신호 로그 기록 (§5.2/§5.3).

북마크/리뷰/경로 서비스의 트랜잭션 내부에서 호출되어 UserActionLog를 생성하고,
커밋 후 P3 실시간 증분 태스크를 큐잉한다.
"""

from django.db import transaction

from apps.place.models import Place
from apps.user.models import User, UserActionLog
from apps.user.services.action_weight_service import compute_final_weight


def record_action(user: User, place: Place, action_type: str, rating: int | None = None) -> UserActionLog:
    """현재 트랜잭션 내에서 UserActionLog를 생성하고, 커밋 후 유저 벡터 증분 갱신을 큐잉한다."""
    weight = compute_final_weight(action_type, place, rating=rating)
    log = UserActionLog.objects.create(
        user=user,
        place=place,
        action_type=action_type,
        weight=weight,
    )

    transaction.on_commit(lambda: _enqueue_incremental_update(user.id, log.id))
    return log


def _enqueue_incremental_update(user_id: int, log_id: int) -> None:
    from apps.user.tasks import update_user_content_vector_incremental

    update_user_content_vector_incremental.delay(user_id, log_id)
