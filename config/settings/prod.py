"""
Production settings.
프로덕션 환경에서 사용되는 설정
"""

from typing import Any

import sentry_sdk
from decouple import config

from .base import *  # noqa: F403

DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(",")

# Security settings
SECURE_SSL_REDIRECT = False  # HTTP → HTTPS 자동 리다이렉트 (암호화되지 않은 접속 차단)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True  # 세션 쿠키를 HTTPS에서만 전송 (세션 탈취 방지)
CSRF_COOKIE_SECURE = True  # CSRF 토큰을 HTTPS에서만 전송 (CSRF 공격 방어)
SECURE_HSTS_SECONDS = 31536000  # 브라우저에게 1년간 HTTPS만 사용하도록 강제 (HTTP 접속 시도 차단)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # 서브도메인도 HTTPS 강제 (서브도메인 공격 차단)
SECURE_HSTS_PRELOAD = True  # HSTS Preload 리스트 등록 가능 (첫 방문부터 HTTPS 강제)
SECURE_BROWSER_XSS_FILTER = True  # XSS 공격 감지 시 브라우저가 차단
SECURE_CONTENT_TYPE_NOSNIFF = True  # MIME 타입 추측 차단 (파일 업로드 공격 방지)
X_FRAME_OPTIONS = "DENY"  # iframe 로딩 차단 (Clickjacking 공격 방지)

# CORS - 프로덕션에서는 명시적으로 허용된 origin만
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS").split(",")

# AWS S3 설정 (선택사항)
USE_S3 = config("USE_S3", default=False, cast=bool)

if USE_S3:
    # AWS S3 Static/Media 파일 설정
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="ap-northeast-2")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

    # Static files
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    # Media files
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Sentry (에러 트래킹 - 선택사항)
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=True,
    )

# DRF - 프로덕션에서는 Browsable API 제거
REST_FRAMEWORK_PROD: dict[str, Any] = REST_FRAMEWORK.copy()  # type: ignore[name-defined,used-before-def]  # noqa: F405
REST_FRAMEWORK_PROD["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
]
REST_FRAMEWORK = REST_FRAMEWORK_PROD

# # 프로덕션 로깅
# LOGGING_PROD: dict[str, Any] = LOGGING.copy()  # type: ignore[name-defined,used-before-def]  # noqa: F405
# LOGGING_PROD["handlers"]["file"] = {
#     "level": "ERROR",
#     "class": "logging.FileHandler",
#     "filename": str(BASE_DIR / "logs" / "django.log"),  # type: ignore[name-defined]  # noqa: F405
#     "formatter": "verbose",
# }
# LOGGING_PROD["root"]["handlers"] = ["console", "file"]
# LOGGING_PROD["loggers"]["django"]["handlers"] = ["console", "file"]
# LOGGING = LOGGING_PROD


sentry_sdk.init(
    dsn=config("SENTRY_DSN", default=""),
    send_default_pii=True,
    environment="production",
)
