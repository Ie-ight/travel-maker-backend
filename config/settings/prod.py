"""
Production settings.
프로덕션 환경에서 사용되는 설정
"""

from decouple import config

from .base import *  # noqa

DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(",")

# Security settings
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

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
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa
    "rest_framework.renderers.JSONRenderer",
]

# 프로덕션 로깅
LOGGING["handlers"]["file"] = {  # noqa
    "level": "ERROR",
    "class": "logging.FileHandler",
    "filename": BASE_DIR / "logs" / "django.log",  # noqa
    "formatter": "verbose",
}

LOGGING["root"]["handlers"] = ["console", "file"]  # noqa
LOGGING["loggers"]["django"]["handlers"] = ["console", "file"]  # noqa
