from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apps.user.serializers.auth_serializer import (
    ErrorDetailSerializer,
    KakaoLoginResponseSerializer,
    KakaoLoginSerializer,
    TokenRefreshResponseSerializer,
)

kakao_login_schema = extend_schema(
    tags=["auth"],
    summary="카카오 소셜 로그인",
    description=(
        "카카오 인가코드(code)를 받아 Access/Refresh 토큰을 발급합니다.\n"
        "- Access Token: 응답 body (`access_token`)\n"
        "- Refresh Token: `Set-Cookie: refresh_token` (HttpOnly)"
    ),
    request=KakaoLoginSerializer,
    responses={
        200: OpenApiResponse(
            response=KakaoLoginResponseSerializer,
            description="기존 유저 로그인 성공",
            examples=[
                OpenApiExample(
                    "기존 유저",
                    value={"access_token": "eyJhbG...", "is_new_user": False},
                )
            ],
        ),
        201: OpenApiResponse(
            response=KakaoLoginResponseSerializer,
            description="신규 유저 가입 + 로그인 성공",
            examples=[
                OpenApiExample(
                    "신규 유저",
                    value={"access_token": "eyJhbG...", "is_new_user": True},
                )
            ],
        ),
        400: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="인가코드 누락",
            examples=[OpenApiExample("400", value={"error_detail": "code가 누락되었습니다."})],
        ),
        401: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="카카오 토큰 검증 실패",
            examples=[OpenApiExample("401", value={"error_detail": "카카오 토큰 검증 실패"})],
        ),
        503: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="카카오 서버 오류",
            examples=[
                OpenApiExample(
                    "503",
                    value={"error_detail": "카카오 서버 불러오기에 실패했습니다."},
                )
            ],
        ),
    },
)

kakao_callback_schema = extend_schema(
    tags=["auth"],
    summary="카카오 OAuth 콜백 (백엔드 전용)",
    description=(
        "카카오 인증 서버가 인가코드를 query param으로 전달하는 콜백입니다.\n"
        "성공: `{FRONTEND_URL}/social-callback?provider=kakao&is_success=true`\n"
        "실패: `{FRONTEND_URL}/social-callback?provider=kakao&is_success=false`"
    ),
    responses={
        302: OpenApiResponse(description="프론트엔드로 리다이렉트"),
        400: OpenApiResponse(response=ErrorDetailSerializer, description="잘못된 요청"),
    },
)

logout_schema = extend_schema(
    tags=["auth"],
    summary="로그아웃",
    description="Cookie의 Refresh Token을 블랙리스트 등록 후 쿠키를 삭제합니다.",
    responses={
        204: OpenApiResponse(description="로그아웃 성공 (No Content)"),
        401: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="인증 실패",
            examples=[
                OpenApiExample(
                    "401",
                    value={"error_detail": "자격 인증 데이터가 제공되지 않았습니다."},
                )
            ],
        ),
    },
)

token_refresh_schema = extend_schema(
    tags=["auth"],
    summary="Access Token 재발급 (Silent Refresh)",
    description=("Cookie의 `refresh_token`으로 새 Access Token을 발급합니다.\n" "Request body는 필요 없습니다."),
    request=None,
    responses={
        200: OpenApiResponse(
            response=TokenRefreshResponseSerializer,
            description="재발급 성공",
            examples=[OpenApiExample("200", value={"access_token": "eyJhbG..."})],
        ),
        403: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="Refresh Token 만료 또는 블랙리스트",
            examples=[
                OpenApiExample(
                    "403",
                    value={"error_detail": "로그인 세션이 만료되었습니다."},
                )
            ],
        ),
    },
)
