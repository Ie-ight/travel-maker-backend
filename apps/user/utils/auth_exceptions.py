from rest_framework import status


class AuthBaseException(Exception):
    """auth 예외 기본 클래스. status_code와 detail을 갖는다."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    default_detail: str = "오류가 발생했습니다."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)

    def __str__(self) -> str:
        return self.detail


# ── 400 Bad Request ──────────────────────────────────────────────────────────


class MissingAuthCodeError(AuthBaseException):
    """카카오 인가코드 누락"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "code가 누락되었습니다."


class InvalidWithdrawReasonError(AuthBaseException):
    """잘못된 탈퇴 사유"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "잘못된 탈퇴 사유입니다."


class UnsupportedProviderError(AuthBaseException):
    """지원하지 않는 소셜 로그인 제공자"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "지원하지 않는 소셜 로그인 제공자입니다."


# ── 401 Unauthorized ─────────────────────────────────────────────────────────


class KakaoTokenVerificationError(AuthBaseException):
    """카카오 토큰 검증 실패"""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "카카오 토큰 검증 실패"


class EmailNotProvidedError(AuthBaseException):
    """카카오 계정에 이메일 미동의"""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "카카오 계정에 이메일이 없습니다. 카카오 설정에서 이메일 제공에 동의해 주세요."


# ── 403 Forbidden ────────────────────────────────────────────────────────────


class SessionExpiredError(AuthBaseException):
    """Refresh Token 없음 / 블랙리스트 / 만료"""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "로그인 세션이 만료되었습니다."


# ── 404 Not Found ────────────────────────────────────────────────────────────


class RecoveryAccountNotFoundError(AuthBaseException):
    """복구 대상 계정 없음"""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "복구할 계정을 찾지 못했습니다."


# ── 409 Conflict ─────────────────────────────────────────────────────────────


class AlreadyWithdrawnError(AuthBaseException):
    """이미 탈퇴한 계정"""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "이미 탈퇴한 계정입니다."


# ── 503 Service Unavailable ──────────────────────────────────────────────────


class KakaoServerError(AuthBaseException):
    """카카오 서버 통신 오류"""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "카카오 서버 불러오기에 실패했습니다."
