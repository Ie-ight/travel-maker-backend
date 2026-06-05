from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apps.user.serializers.auth_serializer import (
    ErrorDetailSerializer,
    KakaoLoginSerializer,
    RecoveryResponseSerializer,
    TokenRefreshResponseSerializer,
    WithdrawSerializer,
)

kakao_callback_schema = extend_schema(
    tags=["auth"],
    summary="카카오 OAuth 콜백 (백엔드 전용)",
    description=(
        "카카오 서버가 리다이렉트하는 콜백 엔드포인트.\n"
        "성공 시 프론트엔드로 302 리다이렉트. Refresh Token은 HttpOnly Cookie로 내려감.\n"
        "프론트엔드는 is_success=true 확인 후 POST /auth/token/refresh 로 access_token 수령."
    ),
    responses={
        302: OpenApiResponse(description="프론트엔드로 리다이렉트 (?is_success=true&is_new_user=bool)"),
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

withdraw_schema = extend_schema(
    tags=["auth"],
    summary="회원 탈퇴",
    description="소프트 딜리트 처리 (is_active=False, deleted_at=탈퇴일시). 탈퇴 후 14일 이내 복구 가능.",
    request=WithdrawSerializer,
    responses={
        204: OpenApiResponse(description="탈퇴 성공 (No Content)"),
        400: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="잘못된 탈퇴 사유",
            examples=[OpenApiExample("400", value={"error_detail": "잘못된 탈퇴 사유입니다."})],
        ),
        401: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="인증 실패",
            examples=[OpenApiExample("401", value={"error_detail": "자격 인증 데이터가 제공되지 않았습니다."})],
        ),
        409: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="이미 탈퇴한 계정",
            examples=[OpenApiExample("409", value={"error_detail": "이미 탈퇴한 계정입니다."})],
        ),
    },
)

recovery_schema = extend_schema(
    tags=["auth"],
    summary="탈퇴 계정 복구",
    description="탈퇴 후 14일 이내 카카오 인가코드로 계정 복구. 복구 시 Access/Refresh 토큰 발급.",
    request=KakaoLoginSerializer,
    responses={
        200: OpenApiResponse(
            response=RecoveryResponseSerializer,
            description="복구 성공",
            examples=[
                OpenApiExample(
                    "200",
                    value={"access_token": "eyJhbG...", "message": "계정이 복구되었습니다."},
                )
            ],
        ),
        404: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="복구 불가 (탈퇴 계정 없음 또는 14일 초과)",
            examples=[OpenApiExample("404", value={"error_detail": "복구할 계정을 찾지 못했습니다."})],
        ),
    },
)
