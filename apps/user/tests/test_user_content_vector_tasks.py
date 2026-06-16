import numpy as np
import pytest

from apps.place.models import Place, PlaceFeature
from apps.user.models import User, UserActionLog, UserPreference
from apps.user.services import behavior_constants
from apps.user.tasks import recompute_user_content_vectors_batch, update_user_content_vector_incremental


@pytest.fixture
def user() -> User:
    return User.objects.create_user(  # type: ignore[attr-defined]
        email="task@test.com", nickname="task_user", gender="M", birthday="2000-01-01"
    )


def _make_place(content_id: int, content_vector: list[float] | None) -> Place:
    place = Place.objects.create(
        place_name=f"place{content_id}",
        latitude="37.1234567",
        longitude="127.1234567",
        content_id=content_id,
        content_type_id=12,
    )
    PlaceFeature.objects.create(
        place=place,
        style_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        content_vector=content_vector,
    )
    return place


@pytest.mark.django_db
class TestUpdateUserContentVectorIncremental:
    def test_S3_미달이면_action_count만_증가하고_벡터는_갱신되지_않는다(self, user: User) -> None:
        place = _make_place(1, [1.0] + [0.0] * 1023)
        log = UserActionLog.objects.create(
            user=user, place=place, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0
        )
        UserPreference.objects.create(user=user, action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD - 2)

        update_user_content_vector_incremental.run(user.id, log.id)

        preference = UserPreference.objects.get(user=user)
        assert preference.action_count == behavior_constants.S3_ACTION_COUNT_THRESHOLD - 1
        assert preference.content_vector is None

        log.refresh_from_db()
        assert log.processed is True

    def test_S3_도달시_content_vector가_증분_갱신된다(self, user: User) -> None:
        place = _make_place(2, [1.0] + [0.0] * 1023)
        log = UserActionLog.objects.create(
            user=user, place=place, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0
        )
        UserPreference.objects.create(user=user, action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD - 1)

        update_user_content_vector_incremental.run(user.id, log.id)

        preference = UserPreference.objects.get(user=user)
        assert preference.action_count == behavior_constants.S3_ACTION_COUNT_THRESHOLD
        assert preference.content_vector is not None
        assert abs(float(np.linalg.norm(preference.content_vector)) - 1.0) < 1e-6

        log.refresh_from_db()
        assert log.processed is True

    def test_이미_처리된_로그는_무시한다(self, user: User) -> None:
        place = _make_place(3, [1.0] + [0.0] * 1023)
        log = UserActionLog.objects.create(
            user=user,
            place=place,
            action_type=UserActionLog.ActionType.BOOKMARK,
            weight=1.0,
            processed=True,
        )

        update_user_content_vector_incremental.run(user.id, log.id)

        assert not UserPreference.objects.filter(user=user).exists()


@pytest.mark.django_db
class TestRecomputeUserContentVectorsBatch:
    def test_S3_유저만_재계산된다(self, user: User) -> None:
        place = _make_place(4, [0.0, 1.0] + [0.0] * 1022)
        UserActionLog.objects.create(user=user, place=place, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0)
        UserPreference.objects.create(user=user, action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD)

        other_user = User.objects.create_user(  # type: ignore[attr-defined]
            email="other@test.com", nickname="other_user", gender="F", birthday="2000-01-01"
        )
        UserPreference.objects.create(user=other_user, action_count=behavior_constants.S3_ACTION_COUNT_THRESHOLD - 1)

        recompute_user_content_vectors_batch.run()

        preference = UserPreference.objects.get(user=user)
        assert preference.content_vector is not None
        assert abs(float(np.linalg.norm(preference.content_vector)) - 1.0) < 1e-6

        other_preference = UserPreference.objects.get(user=other_user)
        assert other_preference.content_vector is None
