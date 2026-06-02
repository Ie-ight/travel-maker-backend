from __future__ import annotations

from typing import Any

from rest_framework import serializers

# ── 요청 Serializer ──────────────────────────────────────────────────────────


class KakaoLoginSerializer(serializers.Serializer[Any]):
    """POST /api/v1/auth/kakao/login"""

    code = serializers.CharField(write_only=True)


# ── 응답 Serializer (Swagger 문서용) ─────────────────────────────────────────


class KakaoLoginResponseSerializer(serializers.Serializer[Any]):
    access_token = serializers.CharField()
    is_new_user = serializers.BooleanField()


class TokenRefreshResponseSerializer(serializers.Serializer[Any]):
    access_token = serializers.CharField()


class ErrorDetailSerializer(serializers.Serializer[Any]):
    error_detail = serializers.CharField()


class WithdrawSerializer(serializers.Serializer[Any]):
    """DELETE /api/v1/auth/withdraw"""

    REASON_CHOICES = ["서비스 불만족", "개인정보", "기타"]
    reason = serializers.ChoiceField(choices=REASON_CHOICES)


class RecoveryResponseSerializer(serializers.Serializer[Any]):
    """POST /api/v1/auth/recovery"""

    access_token = serializers.CharField()
    message = serializers.CharField()
