from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import Token


class BlacklistAwareJWTAuthentication(JWTAuthentication):
    """로그아웃/탈퇴 처리된 access token의 JTI를 블랙리스트에서 검사하는 인증 클래스.

    SimpleJWT 기본 클래스는 refresh token 갱신 시에만 블랙리스트를 확인하므로,
    로그아웃 후에도 access token이 만료 전까지 유효하다는 문제가 있다.
    이 클래스는 모든 인증 요청에서 access token JTI를 블랙리스트에서 조회한다.
    """

    def get_validated_token(self, raw_token: bytes) -> Token:
        token = super().get_validated_token(raw_token)
        # 순환 import 방지를 위해 로컬 import
        from apps.user.services.auth_service import KakaoAuthService

        jti: str = token.get("jti", "")
        if jti and KakaoAuthService.is_jti_blacklisted(jti):
            raise InvalidToken("Token has been blacklisted")
        return token
