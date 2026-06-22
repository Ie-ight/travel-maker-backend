from datetime import timedelta

import pytest
from django.utils import timezone

from apps.user.models import SocialUser, User
from apps.user.tasks import purge_withdrawn_users


def _make_user(email: str, nickname: str) -> User:
    return User.objects.create_user(email=email, nickname=nickname)  # type: ignore[attr-defined]


def _withdraw(user: User, days_ago: int) -> None:
    user.is_active = False
    user.deleted_at = timezone.now() - timedelta(days=days_ago)
    user.save(update_fields=["is_active", "deleted_at"])


@pytest.mark.django_db
class TestPurgeWithdrawnUsers:
    def test_14일_초과_탈퇴_유저_삭제(self) -> None:
        user = _make_user("old@test.com", "old_user")
        _withdraw(user, days_ago=15)

        purge_withdrawn_users()

        assert not User.objects.filter(pk=user.pk).exists()

    def test_14일_미만_1초_탈퇴_유저_보존(self) -> None:
        """14일 경계 직전(14일 - 1초)은 복구 창 안 — 삭제 대상 아님 (__lt 검증)."""
        user = _make_user("exact@test.com", "exact_user")
        user.is_active = False
        user.deleted_at = timezone.now() - timedelta(days=14) + timedelta(seconds=1)
        user.save(update_fields=["is_active", "deleted_at"])

        purge_withdrawn_users()

        assert User.objects.filter(pk=user.pk).exists()

    def test_14일_이내_탈퇴_유저_보존(self) -> None:
        user = _make_user("recent@test.com", "recent_user")
        _withdraw(user, days_ago=13)

        purge_withdrawn_users()

        assert User.objects.filter(pk=user.pk).exists()

    def test_활성_유저_보존(self) -> None:
        user = _make_user("active@test.com", "active_user")

        purge_withdrawn_users()

        assert User.objects.filter(pk=user.pk).exists()

    def test_탈퇴_유저_삭제_시_소셜유저_cascade(self) -> None:
        user = _make_user("social@test.com", "social_user")
        SocialUser.objects.create(user=user, provider=SocialUser.Provider.KAKAO, provider_id="kakao_cascade_test")
        _withdraw(user, days_ago=15)

        purge_withdrawn_users()

        assert not User.objects.filter(pk=user.pk).exists()
        assert not SocialUser.objects.filter(user=user).exists()

    def test_삭제_대상_없을_때_정상_동작(self) -> None:
        purge_withdrawn_users()  # 예외 없이 완료되어야 함
