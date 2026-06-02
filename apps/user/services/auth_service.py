from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction

from apps.user.models import SocialUser, User, generate_nickname
from apps.user.utils.auth_exceptions import (
    AlreadyWithdrawnError,
    EmailNotProvidedError,
    InvalidWithdrawReasonError,
    KakaoServerError,
    KakaoTokenVerificationError,
    MissingAuthCodeError,
    RecoveryAccountNotFoundError,
)

logger = logging.getLogger(__name__)


KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"

_GENDER_MAP = {"male": "M", "female": "F"}


@dataclass
class KakaoUserInfo:
    provider_id: str
    email: str | None
    nickname: str | None
    profile_img_url: str | None
    gender: str | None
    birthday: str | None  # YYYY-MM-DD


class KakaoAuthService:
    """카카오 OAuth2.0 인증 서비스"""

    REFRESH_TOKEN_COOKIE = "refresh_token"
    REFRESH_TOKEN_TTL = 60 * 60 * 24 * 7  # 7일

    # ── 카카오 API 통신 ──────────────────────────────────────────────────────

    @staticmethod
    def get_access_token(code: str) -> str:
        """인가코드로 카카오 액세스 토큰 발급"""
        try:
            response = requests.post(
                KAKAO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.KAKAO_CLIENT_ID,  # type: ignore[misc]
                    "redirect_uri": settings.KAKAO_REDIRECT_URI,  # type: ignore[misc]
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise KakaoServerError() from e

        data = response.json()
        if "error" in data:
            raise KakaoTokenVerificationError()

        access_token = data.get("access_token")
        if not access_token:
            raise KakaoServerError()

        return str(access_token)

    @staticmethod
    def get_user_info(access_token: str) -> KakaoUserInfo:
        """카카오 액세스 토큰으로 유저 정보 조회"""
        try:
            response = requests.get(
                KAKAO_USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise KakaoServerError() from e

        data = response.json()
        account = data.get("kakao_account", {})
        profile = account.get("profile", {})

        raw_gender = account.get("gender")
        gender = _GENDER_MAP.get(raw_gender) if raw_gender else None

        birthyear = account.get("birthyear")
        birthday_mmdd = account.get("birthday")
        if birthyear and birthday_mmdd and len(birthday_mmdd) == 4:
            birthday = f"{birthyear}-{birthday_mmdd[:2]}-{birthday_mmdd[2:]}"
        else:
            birthday = None

        return KakaoUserInfo(
            provider_id=str(data["id"]),
            email=account.get("email"),
            nickname=profile.get("nickname"),
            profile_img_url=profile.get("profile_image_url"),
            gender=gender,
            birthday=birthday,
        )

    # ── 유저 조회 / 생성 ─────────────────────────────────────────────────────

    @classmethod
    def get_or_create_user(cls, code: str) -> tuple[User, bool]:
        """
        인가코드로 유저 조회 또는 신규 생성
        Returns: (user, is_new_user)
        """
        if not code:
            raise MissingAuthCodeError()

        access_token = cls.get_access_token(code)
        user_info = cls.get_user_info(access_token)

        if not user_info.email:
            raise EmailNotProvidedError()

        with transaction.atomic():
            try:
                social_user = SocialUser.objects.select_related("user").get(
                    provider=SocialUser.Provider.KAKAO,
                    provider_id=user_info.provider_id,
                )
                return social_user.user, False
            except SocialUser.DoesNotExist:
                pass

            try:
                user = User.objects.create_user(
                    email=user_info.email,
                    nickname=generate_nickname(),
                    gender=user_info.gender,
                    birthday=user_info.birthday or "1900-01-01",
                    profile_img_url=user_info.profile_img_url or "",
                )
                user.set_unusable_password()
                user.save(update_fields=["password"])
                SocialUser.objects.create(
                    user=user,
                    provider=SocialUser.Provider.KAKAO,
                    provider_id=user_info.provider_id,
                )
            except IntegrityError:
                # 동시 요청으로 이미 생성된 경우
                social_user = SocialUser.objects.select_related("user").get(
                    provider=SocialUser.Provider.KAKAO,
                    provider_id=user_info.provider_id,
                )
                return social_user.user, False

        return user, True

    WITHDRAW_REASONS = {"서비스 불만족", "개인정보", "기타"}
    RECOVERY_WINDOW_DAYS = 14

    @classmethod
    def withdraw_user(cls, user: User, reason: str) -> None:
        """회원 탈퇴: 소프트 딜리트 (is_active=False, deleted_at=now())"""
        if reason not in cls.WITHDRAW_REASONS:
            raise InvalidWithdrawReasonError()

        if not user.is_active:
            raise AlreadyWithdrawnError()

        from django.utils import timezone

        user.is_active = False
        user.deleted_at = timezone.now()
        user.save(update_fields=["is_active", "deleted_at"])

    @classmethod
    def recover_user(cls, code: str) -> User:
        """
        탈퇴 계정 복구: 14일 이내 재로그인 시 is_active 복원
        Returns: 복구된 user
        """
        if not code:
            raise MissingAuthCodeError()

        access_token = cls.get_access_token(code)
        user_info = cls.get_user_info(access_token)

        try:
            social_user = SocialUser.objects.select_related("user").get(
                provider=SocialUser.Provider.KAKAO,
                provider_id=user_info.provider_id,
            )
        except SocialUser.DoesNotExist:
            raise RecoveryAccountNotFoundError() from None

        user = social_user.user
        if user.is_active:
            raise RecoveryAccountNotFoundError()

        from django.utils import timezone

        if user.deleted_at is None or timezone.now() > user.deleted_at + timedelta(days=cls.RECOVERY_WINDOW_DAYS):
            raise RecoveryAccountNotFoundError()

        user.is_active = True
        user.deleted_at = None
        user.save(update_fields=["is_active", "deleted_at"])
        return user

    # ── JWT 토큰 ─────────────────────────────────────────────────────────────

    @staticmethod
    def generate_token_pair(user: User) -> tuple[str, str]:
        """JWT Access / Refresh 토큰 쌍 발급. Returns: (access_token, refresh_token)"""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    # ── 토큰 블랙리스트 ──────────────────────────────────────────────────────

    @staticmethod
    def blacklist_token(refresh_token_str: str) -> None:
        """Refresh Token을 Redis 캐시에 블랙리스트 등록"""
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.tokens import RefreshToken

        try:
            token = RefreshToken(refresh_token_str)  # type: ignore[arg-type]
            jti: str = token.payload.get("jti", "")
            exp: int = token.payload.get("exp", 0)
            ttl = exp - int(time.time())
            if ttl > 0 and jti:
                cache.set(f"blacklist_{jti}", "true", ttl)
        except TokenError:
            pass  # 이미 만료된 토큰
        except Exception:
            logger.error("토큰 블랙리스트 등록 실패", exc_info=True)

    @staticmethod
    def is_jti_blacklisted(jti: str) -> bool:
        """jti로 블랙리스트 여부 확인. 캐시 장애 시 False(fail-open) 반환."""
        try:
            return bool(cache.get(f"blacklist_{jti}"))
        except Exception:
            logger.error("블랙리스트 조회 실패 (캐시 장애), fail-open 처리", exc_info=True)
            return False

    @staticmethod
    def is_blacklisted(refresh_token_str: str) -> bool:
        """토큰 문자열로 블랙리스트 여부 확인"""
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.tokens import RefreshToken

        try:
            token = RefreshToken(refresh_token_str)  # type: ignore[arg-type]
            jti = token.payload.get("jti", "")
            return KakaoAuthService.is_jti_blacklisted(jti)
        except TokenError:
            return True
