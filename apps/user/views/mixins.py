from typing import Never

from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request


class AuthRequiredMixin:
    """미인증 요청을 401 NotAuthenticated로 응답하기 위한 공통 permission_denied 오버라이드."""

    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> Never:
        raise NotAuthenticated("자격 인증 데이터가 제공되지 않았습니다.")
