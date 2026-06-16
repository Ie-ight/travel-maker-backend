from datetime import timedelta

import numpy as np
import pytest
from django.utils import timezone

from apps.place.models import Place, PlaceFeature
from apps.user.models import User, UserActionLog
from apps.user.services import behavior_constants
from apps.user.services.user_content_vector_service import (
    apply_incremental_update,
    compute_user_content_vector,
    compute_user_content_vector_for_user,
    should_be_s3,
)


@pytest.fixture
def user() -> User:
    return User.objects.create_user(  # type: ignore[attr-defined]
        email="vec@test.com", nickname="vec_user", gender="M", birthday="2000-01-01"
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
class TestShouldBeS3:
    def test_threshold_미달이면_False(self) -> None:
        assert should_be_s3(behavior_constants.S3_ACTION_COUNT_THRESHOLD - 1) is False

    def test_threshold_이상이면_True(self) -> None:
        assert should_be_s3(behavior_constants.S3_ACTION_COUNT_THRESHOLD) is True


@pytest.mark.django_db
class TestComputeUserContentVector:
    def test_정규화된_벡터를_반환한다(self, user: User) -> None:
        place = _make_place(1, [1.0] + [0.0] * 1023)
        log = UserActionLog.objects.create(
            user=user, place=place, action_type=UserActionLog.ActionType.BOOKMARK, weight=0.8
        )

        vector = compute_user_content_vector([log], apply_decay=False)

        assert vector is not None
        assert vector.shape == (1024,)
        assert math_isclose(float(np.linalg.norm(vector)), 1.0)

    def test_content_vector가_없는_장소는_제외된다(self, user: User) -> None:
        place = _make_place(2, None)
        log = UserActionLog.objects.create(
            user=user, place=place, action_type=UserActionLog.ActionType.BOOKMARK, weight=0.8
        )

        vector = compute_user_content_vector([log], apply_decay=False)

        assert vector is None

    def test_합산결과가_영벡터면_None을_반환한다(self, user: User) -> None:
        place_a = _make_place(3, [1.0] + [0.0] * 1023)
        place_b = _make_place(4, [1.0] + [0.0] * 1023)
        log_a = UserActionLog.objects.create(
            user=user, place=place_a, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0
        )
        log_b = UserActionLog.objects.create(
            user=user, place=place_b, action_type=UserActionLog.ActionType.UNBOOKMARK, weight=-1.0
        )

        vector = compute_user_content_vector([log_a, log_b], apply_decay=False)

        assert vector is None

    def test_decay가_적용되면_오래된_로그의_영향이_줄어든다(self, user: User) -> None:
        place_old = _make_place(5, [1.0] + [0.0] * 1023)
        place_new = _make_place(6, [0.0, 1.0] + [0.0] * 1022)

        now = timezone.now()
        log_old = UserActionLog.objects.create(
            user=user, place=place_old, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0
        )
        log_old.created_at = now - timedelta(days=365)
        log_old.save(update_fields=["created_at"])

        log_new = UserActionLog.objects.create(
            user=user, place=place_new, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0
        )
        log_new.created_at = now
        log_new.save(update_fields=["created_at"])

        vector = compute_user_content_vector(
            [UserActionLog.objects.get(pk=log_old.pk), UserActionLog.objects.get(pk=log_new.pk)],
            apply_decay=True,
            now=now,
        )

        assert vector is not None
        assert vector[1] > vector[0]


@pytest.mark.django_db
class TestApplyIncrementalUpdate:
    def test_기존벡터가_None이면_새로_생성한다(self) -> None:
        vector = apply_incremental_update(None, 1.0, [1.0] + [0.0] * 1023)

        assert vector is not None
        assert math_isclose(float(np.linalg.norm(vector)), 1.0)
        assert math_isclose(float(vector[0]), 1.0)

    def test_기존벡터에_가산후_재정규화한다(self) -> None:
        current = np.zeros(1024, dtype=np.float64)
        current[0] = 1.0

        vector = apply_incremental_update(current, 1.0, [0.0, 1.0] + [0.0] * 1022)

        assert vector is not None
        assert math_isclose(float(np.linalg.norm(vector)), 1.0)
        assert vector[0] > 0
        assert vector[1] > 0

    def test_상쇄되어_영벡터가되면_None을_반환한다(self) -> None:
        current = np.zeros(1024, dtype=np.float64)
        current[0] = 1.0

        vector = apply_incremental_update(current, -1.0, [1.0] + [0.0] * 1023)

        assert vector is None


@pytest.mark.django_db
class TestComputeUserContentVectorForUser:
    def test_lookback_범위_밖의_로그는_제외된다(self, user: User) -> None:
        place_recent = _make_place(7, [1.0] + [0.0] * 1023)
        place_old = _make_place(8, [0.0, 1.0] + [0.0] * 1022)

        now = timezone.now()

        recent_log = UserActionLog.objects.create(
            user=user, place=place_recent, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0
        )
        recent_log.created_at = now
        recent_log.save(update_fields=["created_at"])

        old_log = UserActionLog.objects.create(
            user=user, place=place_old, action_type=UserActionLog.ActionType.BOOKMARK, weight=1.0
        )
        old_log.created_at = now - timedelta(days=behavior_constants.BEHAVIOR_LOOKBACK_DAYS + 1)
        old_log.save(update_fields=["created_at"])

        vector = compute_user_content_vector_for_user(user, apply_decay=False, now=now)

        assert vector is not None
        assert math_isclose(float(vector[0]), 1.0)
        assert math_isclose(float(vector[1]), 0.0)


def math_isclose(a: float, b: float, *, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol
