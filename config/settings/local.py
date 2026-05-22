"""
Local development settings.
로컬 개발 환경에서 사용되는 설정
"""

from .base import *  # noqa
from typing import Any

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# 개발 환경에서는 CORS 전체 허용 (선택사항)
CORS_ALLOW_ALL_ORIGINS = True

# Django Debug Toolbar (선택사항)
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
# INTERNAL_IPS = ["127.0.0.1"]

# 개발 환경에서는 이메일을 콘솔에 출력
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# 개발용 로깅 레벨
LOGGING_LOCAL: dict[str, Any] = LOGGING.copy()  # type: ignore[name-defined,used-before-def]  # noqa: F405
LOGGING_LOCAL["root"]["level"] = "DEBUG"
LOGGING_LOCAL["loggers"]["django"]["level"] = "DEBUG"
LOGGING = LOGGING_LOCAL

# Static/Media 파일 로컬 저장
USE_S3 = False
