from __future__ import annotations

import random
from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models

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
        **extra_fields: bool | str | None,
    ) -> User:
        email = self.normalize_email(email)
        user: User = self.model(email=email, nickname=nickname, **extra_fields)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        nickname: str,
        **extra_fields: bool | str | None,
    ) -> User:
        extra_fields["role"] = "ADMIN"
        extra_fields["is_active"] = True
        extra_fields["is_staff"] = True
        return self.create_user(email, nickname, **extra_fields)


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
    gender = models.CharField(choices=Gender.choices, max_length=6, null=True, verbose_name="성별")
    birthday = models.DateField(null=False, verbose_name="생년월일")
    profile_img_url = models.CharField(max_length=255, blank=True, null=False, verbose_name="프로필 이미지 URL")
    tags = models.ManyToManyField("place.Tag", blank=True, related_name="users", verbose_name="관심 태그")
    is_active = models.BooleanField(default=True, verbose_name="활성 여부")
    is_staff = models.BooleanField(default=False, verbose_name="스태프 여부")
    role = models.CharField(choices=Role.choices, default=Role.USER, verbose_name="권한")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="탈퇴 일시")

    USERNAME_FIELD: ClassVar[str] = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["nickname", "gender", "birthday"]

    objects: ClassVar[CustomUserManager] = CustomUserManager()  # type: ignore[misc]

    def has_perm(self, perm: str, obj: object = None) -> bool:  # type: ignore[override]
        return self.role == self.Role.ADMIN

    def has_module_perms(self, app_label: str) -> bool:
        return self.role == self.Role.ADMIN

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

    class Meta:
        db_table = "social_users"
        verbose_name = "소셜 유저"
        verbose_name_plural = "소셜 유저 목록"


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers", verbose_name="팔로워")
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followings", verbose_name="팔로잉")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="팔로우 일시")

    class Meta:
        db_table = "follow"
        constraints = [models.UniqueConstraint(fields=["follower", "following"], name="unique_follow")]
        verbose_name = "팔로우"
        verbose_name_plural = "팔로우 목록"
