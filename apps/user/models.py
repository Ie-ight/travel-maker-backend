from __future__ import annotations

import random
from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from pgvector.django import VectorField

from apps.core.models import TimeStampModel

_MAX_NICKNAME_RETRIES = 50


def generate_nickname() -> str:
    for _ in range(_MAX_NICKNAME_RETRIES):
        number = random.randint(10000, 99999)
        nickname = f"traveler_{number}"
        if not User.objects.filter(nickname=nickname).exists():
            return nickname
    raise RuntimeError("닉네임 생성 실패: 재시도 횟수 초과")


class CustomUserManager(BaseUserManager["User"]):
    def create_user(
        self,
        email: str,
        nickname: str,
        password: str | None = None,
        **extra_fields: bool | str | None,
    ) -> User:
        email = self.normalize_email(email)
        user: User = self.model(email=email, nickname=nickname, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        nickname: str,
        password: str | None = None,
        **extra_fields: bool | str | None,
    ) -> User:
        extra_fields["role"] = "ADMIN"
        extra_fields["is_active"] = True
        extra_fields["is_staff"] = True
        return self.create_user(email, nickname, password, **extra_fields)


class User(AbstractBaseUser, TimeStampModel):
    class Gender(models.TextChoices):
        MALE = "M", "남성"
        FEMALE = "F", "여성"

    class Role(models.TextChoices):
        USER = "USER", "일반유저"
        ADMIN = "ADMIN", "관리자"

    email = models.EmailField(max_length=255, null=False, unique=True, verbose_name="이메일")
    nickname = models.CharField(max_length=14, null=False, unique=True, verbose_name="닉네임")
    bio = models.CharField(max_length=100, blank=True, default="", verbose_name="자기소개")
    gender = models.CharField(choices=Gender.choices, max_length=6, null=True, blank=True, verbose_name="성별")
    birthday = models.DateField(null=True, blank=True, verbose_name="생년월일")
    profile_img_url = models.CharField(max_length=255, blank=True, null=False, verbose_name="프로필 이미지 URL")
    tags = models.ManyToManyField("place.Tag", blank=True, related_name="users", verbose_name="관심 태그")
    is_active = models.BooleanField(default=True, verbose_name="활성 여부")
    is_staff = models.BooleanField(default=False, verbose_name="스태프 여부")
    role = models.CharField(choices=Role.choices, default=Role.USER, verbose_name="권한")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="탈퇴 일시")

    USERNAME_FIELD: ClassVar[str] = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["nickname"]

    objects: ClassVar[CustomUserManager] = CustomUserManager()  # type: ignore[misc]

    def has_perm(self, perm: str, obj: object = None) -> bool:  # type: ignore[override]
        return self.role == self.Role.ADMIN

    def has_module_perms(self, app_label: str) -> bool:
        return self.role == self.Role.ADMIN

    def get_all_permissions(self, obj: object = None) -> set[str]:
        """어드민 테마 적용을 위해서 필요"""
        return set()

    def __str__(self) -> str:
        return f"{self.nickname} ({self.email})"

    class Meta:
        db_table = "user"
        verbose_name = "유저"
        verbose_name_plural = "유저 목록"


class SocialUser(TimeStampModel):
    class Provider(models.TextChoices):
        KAKAO = "kakao", "카카오"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_users", verbose_name="유저")
    provider = models.CharField(max_length=10, choices=Provider.choices, verbose_name="제공자")
    provider_id = models.CharField(max_length=255, verbose_name="제공자 ID")

    def __str__(self) -> str:
        return f"{self.user.nickname} - {self.provider}"

    class Meta:
        db_table = "social_users"
        verbose_name = "소셜 유저"
        verbose_name_plural = "소셜 유저 목록"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_id"],
                name="unique_provider_account",
            )
        ]


class UserPreference(TimeStampModel):
    """행동 기반 개인화(S3) 정렬 벡터. action_count가 임계값(behavior_constants.S3_ACTION_COUNT_THRESHOLD)
    이상이 되면 content_vector가 채워지고, 그 전까지는 null로 유지되어 S2(퀴즈 6축)가 적용된다."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preference", verbose_name="유저")
    content_vector = VectorField(dimensions=1024, null=True, blank=True, verbose_name="행동 기반 임베딩 벡터")
    action_count = models.PositiveIntegerField(default=0, verbose_name="누적 행동 수")

    class Meta:
        db_table = "user_preferences"
        verbose_name = "유저 행동 선호"
        verbose_name_plural = "유저 행동 선호 목록"

    def __str__(self) -> str:
        return f"{self.user.nickname} (action_count={self.action_count})"


class UserActionLog(models.Model):
    """행동 신호 로그. 가중치(weight)는 생성 시점에 §6/§7 공식으로 계산되어 저장된다."""

    class ActionType(models.TextChoices):
        REVIEW = "review", "리뷰"
        BOOKMARK = "bookmark", "북마크"
        UNBOOKMARK = "unbookmark", "북마크 해제"
        ROUTE_ADD = "route_add", "경로 추가"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="action_logs", verbose_name="유저")
    place = models.ForeignKey("place.Place", on_delete=models.CASCADE, related_name="action_logs", verbose_name="장소")
    action_type = models.CharField(max_length=20, choices=ActionType.choices, verbose_name="행동 유형")
    weight = models.FloatField(verbose_name="가중치")
    processed = models.BooleanField(default=False, verbose_name="유저 벡터 반영 여부")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="발생 일시")

    class Meta:
        db_table = "user_action_logs"
        indexes = [
            models.Index(fields=["user", "place", "action_type"], name="useraction_user_place_type_idx"),
            models.Index(fields=["processed"], condition=Q(processed=False), name="useraction_unprocessed_idx"),
        ]
        verbose_name = "유저 행동 로그"
        verbose_name_plural = "유저 행동 로그 목록"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.place_id}:{self.action_type}={self.weight}"


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers", verbose_name="팔로워")
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followings", verbose_name="팔로잉")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="팔로우 일시")

    def __str__(self) -> str:
        return f"{self.follower.nickname} → {self.following.nickname}"

    class Meta:
        db_table = "follow"
        constraints = [models.UniqueConstraint(fields=["follower", "following"], name="unique_follow")]
        verbose_name = "팔로우"
        verbose_name_plural = "팔로우 목록"
