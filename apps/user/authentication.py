from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.exceptions import InvalidToken


class BlacklistAwareJWTAuthentication(OpenApiAuthenticationExtension):  # type: ignore[misc]
    """로그아웃/탈퇴 처리된 access token의 JTI를 블랙리스트에서 검사하는 인증 클래스.

    SimpleJWT 기본 클래스는 refresh token 갱신 시에만 블랙리스트를 확인하므로,
    로그아웃 후에도 access token이 만료 전까지 유효하다는 문제가 있다.
    이 클래스는 모든 인증 요청에서 access token JTI를 블랙리스트에서 조회한다.

    만료·유효하지 않은 토큰은 None 반환(익명 처리)으로 처리한다.
    permission_classes = [IsAuthenticated] 인 뷰는 이후 NotAuthenticated(401)로 차단되므로
    동작은 동일하다. permission_classes = [] 인 공개 뷰에서는 토큰 만료로 인한 오탐 401을 방지한다.
    블랙리스트 토큰은 명시적 InvalidToken(401)을 유지한다.
    """

    target_class = "apps.user.authentication.BlacklistAwareJWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, str]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }

    def authenticate(self, request: Request) -> tuple[object, object] | None:  # type: ignore[override]
        try:
            result = super().authenticate(request)
        except AuthenticationFailed:
            # 만료·서명 불일치 등 유효하지 않은 토큰 → 익명 처리
            return None

        if result is None:
            return None

        # 순환 import 방지를 위해 로컬 import
        from apps.user.services.auth_service import KakaoAuthService

        _, validated_token = result
        jti: str = validated_token.get("jti", "")
        if jti and KakaoAuthService.is_jti_blacklisted(jti):
            raise InvalidToken("Token has been blacklisted")
        return result
