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
        return self.create_user(email, nickname, **extra_fields)


class User(AbstractBaseUser, TimeStampModel):
    class Gender(models.TextChoices):
        MALE = "M", "남성"
        FEMALE = "F", "여성"

    class Role(models.TextChoices):
        USER = "USER", "일반유저"
        ADMIN = "ADMIN", "관리자"

    email = models.EmailField(max_length=255, null=False, unique=True)
    nickname = models.CharField(max_length=14, null=False, unique=True)
    gender = models.CharField(choices=Gender.choices, max_length=6, null=True)
    birthday = models.DateField(null=False)
    profile_img_url = models.CharField(max_length=255, blank=True, null=False)
    is_active = models.BooleanField(default=True)
    role = models.CharField(choices=Role.choices, default=Role.USER)

    USERNAME_FIELD: ClassVar[str] = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["nickname", "gender", "birthday"]

    objects: ClassVar[CustomUserManager] = CustomUserManager()  # type: ignore[misc]

    class Meta:
        db_table = "user"


class SocialUser(TimeStampModel):
    class Provider(models.TextChoices):
        KAKAO = "kakao", "카카오"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_users")
    provider = models.CharField(max_length=10, choices=Provider.choices)
    provider_id = models.CharField(max_length=255)

    class Meta:
        db_table = "social_users"
