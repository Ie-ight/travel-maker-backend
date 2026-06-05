from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpResponseBase, HttpResponseRedirect
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.user.schemas.auth_schemas import (
    kakao_callback_schema,
    kakao_login_schema,
    logout_schema,
    recovery_schema,
    token_refresh_schema,
    withdraw_schema,
)
from apps.user.serializers.auth_serializer import KakaoLoginSerializer, WithdrawSerializer
from apps.user.services.auth_service import KakaoAuthService
from apps.user.utils.auth_exceptions import (
    AuthBaseException,
    MissingAuthCodeError,
    SessionExpiredError,
)

REFRESH_COOKIE = KakaoAuthService.REFRESH_TOKEN_COOKIE
REFRESH_TTL = KakaoAuthService.REFRESH_TOKEN_TTL
logger = logging.getLogger(__name__)


def _set_refresh_cookie(response: HttpResponseBase, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        max_age=REFRESH_TTL,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/")


# ── 카카오 로그인 (POST) ─────────────────────────────────────────────────────


class KakaoLoginView(APIView):
    """
    POST /api/v1/auth/kakao/login

    카카오 인가코드로 로그인 처리.
    - 기존 유저: 200
    - 신규 가입: 201
    - Refresh Token은 HttpOnly Cookie로 내려감
    """

    permission_classes = []

    @kakao_login_schema
    def post(self, request: Request) -> Response:
        serializer = KakaoLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error_detail": MissingAuthCodeError.default_detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code: str = serializer.validated_data["code"]
        logger.info(f"카카오 로그인 시도: code={code[:10]}...")

        try:
            user, is_new_user = KakaoAuthService.get_or_create_user(code)
            logger.info(f"카카오 로그인 성공: user={user.email}, is_new_user={is_new_user}")
        except AuthBaseException as e:
            logger.error(f"카카오 로그인 실패: {e.detail}")
            return Response({"error_detail": e.detail}, status=e.status_code)

        try:
            user, is_new_user = KakaoAuthService.get_or_create_user(code)
        except AuthBaseException as e:
            return Response({"error_detail": e.detail}, status=e.status_code)

        access_token, refresh_token = KakaoAuthService.generate_token_pair(user)
        http_status = status.HTTP_201_CREATED if is_new_user else status.HTTP_200_OK

        response = Response(
            {"access_token": access_token, "is_new_user": is_new_user},
            status=http_status,
        )
        _set_refresh_cookie(response, refresh_token)
        return response


# ── 카카오 콜백 (GET, 302 redirect) ─────────────────────────────────────────


class KakaoCallbackView(APIView):
    """
    GET /api/v1/auth/kakao/callback

    카카오 서버가 리다이렉트하는 콜백 엔드포인트 (백엔드 전용).
    성공 시 프론트엔드로 302 리다이렉트.
    """

    permission_classes = []

    @kakao_callback_schema
    def get(self, request: Request) -> HttpResponseRedirect:
        frontend_url = getattr(settings, "FRONTEND_URL", "")
        code = request.query_params.get("code")
        error = request.query_params.get("error")

        if error or not code:
            return redirect(f"{frontend_url}/social-callback?provider=kakao&is_success=false")

        try:
            user, is_new_user = KakaoAuthService.get_or_create_user(code)
        except Exception:
            return redirect(f"{frontend_url}/social-callback?provider=kakao&is_success=false")

        access_token, refresh_token = KakaoAuthService.generate_token_pair(user)
        response = redirect(
            f"{frontend_url}/social-callback?provider=kakao&is_success=true&is_new_user={str(is_new_user).lower()}"
        )
        _set_refresh_cookie(response, refresh_token)
        return response


# ── 로그아웃 ─────────────────────────────────────────────────────────────────


class LogoutView(APIView):
    """POST /api/v1/auth/logout"""

    permission_classes = [IsAuthenticated]

    @logout_schema
    def post(self, request: Request) -> Response:
        refresh_token = request.COOKIES.get(REFRESH_COOKIE)
        if refresh_token:
            KakaoAuthService.blacklist_token(refresh_token)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


# ── 토큰 재발급 ──────────────────────────────────────────────────────────────


class TokenRefreshView(APIView):
    """POST /api/v1/auth/token/refresh"""

    permission_classes = []

    @token_refresh_schema
    def post(self, request: Request) -> Response:
        refresh_token_str = request.COOKIES.get(REFRESH_COOKIE)

        if not refresh_token_str:
            return Response(
                {"error_detail": SessionExpiredError.default_detail},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            token = RefreshToken(refresh_token_str)  # type: ignore[arg-type]
        except TokenError:
            return Response(
                {"error_detail": SessionExpiredError.default_detail},
                status=status.HTTP_403_FORBIDDEN,
            )

        jti: str = token.payload.get("jti", "")
        if KakaoAuthService.is_jti_blacklisted(jti):
            return Response(
                {"error_detail": SessionExpiredError.default_detail},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {"access_token": str(token.access_token)},
            status=status.HTTP_200_OK,
        )


# ── 회원 탈퇴 ────────────────────────────────────────────────────────────────


class WithdrawView(APIView):
    """DELETE /api/v1/auth/withdraw"""

    permission_classes = [IsAuthenticated]

    @withdraw_schema
    def delete(self, request: Request) -> Response:
        serializer = WithdrawSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error_detail": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason: str = serializer.validated_data["reason"]

        try:
            KakaoAuthService.withdraw_user(request.user, reason)  # type: ignore[arg-type]
        except AuthBaseException as e:
            return Response({"error_detail": e.detail}, status=e.status_code)

        refresh_token = request.COOKIES.get(REFRESH_COOKIE)
        if refresh_token:
            KakaoAuthService.blacklist_token(refresh_token)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


# ── 탈퇴 계정 복구 ───────────────────────────────────────────────────────────


class RecoveryView(APIView):
    """POST /api/v1/auth/recovery"""

    permission_classes = []

    @recovery_schema
    def post(self, request: Request) -> Response:
        serializer = KakaoLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error_detail": MissingAuthCodeError.default_detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code: str = serializer.validated_data["code"]

        try:
            user = KakaoAuthService.recover_user(code)
        except AuthBaseException as e:
            return Response({"error_detail": e.detail}, status=e.status_code)

        access_token, refresh_token = KakaoAuthService.generate_token_pair(user)
        response = Response(
            {"access_token": access_token, "message": "계정이 복구되었습니다."},
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, refresh_token)
        return response
