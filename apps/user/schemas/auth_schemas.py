from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apps.user.serializers.auth_serializer import (
    AdminLoginResponseSerializer,
    AdminLoginSerializer,
    ErrorDetailSerializer,
    KakaoLoginResponseSerializer,
    KakaoLoginSerializer,
    RecoveryResponseSerializer,
    TokenRefreshResponseSerializer,
    WithdrawSerializer,
)

kakao_callback_schema = extend_schema(
    tags=["auth"],
    summary="카카오 소셜 로그인 콜백 (백엔드 주도)",
    description=(
        "Kakao가 인가코드를 쿼리 파라미터로 전달하는 백엔드 주도 OAuth2 콜백.\n"
        "처리 후 프론트엔드로 302 리다이렉트한다.\n"
        "- 성공: `FRONTEND_URL/auth/callback?access_token=...&is_new_user=...`\n"
        "- 실패: `FRONTEND_URL/auth/callback?error=auth_failed`\n"
        "- Refresh Token: `Set-Cookie: refresh_token` (HttpOnly)"
    ),
    responses={
        302: OpenApiResponse(description="프론트엔드로 리다이렉트"),
    },
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
    description=(
        "Cookie의 `refresh_token`으로 새 Access/Refresh Token을 재발급합니다.\n기존 Refresh Token은 폐기되고 새 토큰이 Cookie에 설정됩니다. Request body는 필요 없습니다."
    ),
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

admin_login_schema = extend_schema(
    tags=["auth"],
    summary="어드민 로그인 (Swagger 테스트용)",
    description=(
        "이메일 + 패스워드로 JWT Access Token을 발급합니다.\n"
        "**비밀번호가 설정된 활성 계정만 사용 가능합니다.**\n\n"
        "Swagger 테스트 목적으로만 사용하세요. "
        "카카오 소셜 로그인 유저는 비밀번호가 없으므로 사용 불가합니다."
    ),
    request=AdminLoginSerializer,
    responses={
        200: OpenApiResponse(
            response=AdminLoginResponseSerializer,
            description="로그인 성공",
            examples=[OpenApiExample("200", value={"access_token": "eyJhbG..."})],
        ),
        401: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="이메일/패스워드 불일치 또는 staff 권한 없음",
            examples=[OpenApiExample("401", value={"error_detail": "이메일 또는 패스워드가 올바르지 않습니다."})],
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
