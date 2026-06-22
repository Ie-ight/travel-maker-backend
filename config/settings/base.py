"""
Django settings for travel-maker project.
Base settings - 모든 환경에서 공통으로 사용되는 설정
"""

import os
from datetime import timedelta
from pathlib import Path

from decouple import config  # type: ignore

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-this-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")


# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "django_celery_beat",
]

LOCAL_APPS = [
    "apps.user",
    "apps.core",
    "apps.place",
    "apps.review",
    "apps.bookmark",
    "apps.travel_quiz",
    "apps.route",
    "apps.share",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "user.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="travel_maker_db"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="postgres"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60,  # 커넥션을 60초간 재사용하여 매 요청 TCP 연결 비용 제거
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = config("LANGUAGE_CODE", default="ko-kr")
TIME_ZONE = config("TIME_ZONE", default="Asia/Seoul")
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.user.authentication.BlacklistAwareJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exception_handler.custom_exception_handler",
}

# DRF Spectacular 설정 추가
SPECTACULAR_SETTINGS = {
    "TITLE": "Travel Maker API",
    "DESCRIPTION": "여행 추천 플랫폼 API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
    "DEFAULT_AUTHENTICATION_EXTENSIONS": [
        "drf_spectacular.extensions.OpenApiAuthenticationExtension",
    ],
}

# Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("JWT_ACCESS_TOKEN_LIFETIME", default=60, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_REFRESH_TOKEN_LIFETIME", default=10080, cast=int)
    ),  # 7일 = 쿠키 TTL과 일치
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("JWT_SECRET_KEY", default=SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# CORS settings
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000,http://localhost:8080").split(",")

CORS_ALLOW_CREDENTIALS = True


# Celery Configuration
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE


# Redis Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{config('REDIS_HOST', default='localhost')}:{config('REDIS_PORT', default='6379')}/0",
    }
}


# Email Configuration
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@travel-maker.com")


# 한국관광공사 Tour API (KorService2)
TOUR_API_CODE = config("TOUR_API_CODE", default="")
# 대량 수집용 추가 키(키당 일 1000건 한도 → 소진 시 순차 전환). 존재하는 것만 순서대로 모은다.
TOUR_API_CODES = [
    key for key in (TOUR_API_CODE, *(config(f"TOUR_API_CODE{i}", default="") for i in range(2, 21))) if key
]
TOUR_API_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
# 호출 간 최소 간격(초). 버스트 방지용 얇은 마진(429는 속도가 아닌 키 누적 한도라 큰 딜레이 불필요). 0이면 끔.
TOUR_API_MIN_INTERVAL = config("TOUR_API_MIN_INTERVAL", default=0.05, cast=float)

# AI 태깅 (provider 토글: gemini | ollama)
AI_TAGGING_PROVIDER = config("AI_TAGGING_PROVIDER", default="gemini")
# Gemini (Google AI Studio)
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
GEMINI_MODEL = config("GEMINI_MODEL", default="gemini-2.5-flash-lite")
# Ollama (로컬 Gemma 등) — 컨테이너에서 호스트 Ollama 접근(Ollama는 OLLAMA_HOST=0.0.0.0로 기동 필요할 수 있음)
OLLAMA_HOST = config("OLLAMA_HOST", default="http://host.docker.internal:11434")
OLLAMA_MODEL = config("OLLAMA_MODEL", default="gemma3:12b")
# 배포 환경은 ollama 부재 → Gemini로만 태깅. 일일 스케줄 태스크의 Gemini 한도(무료 등급: 일 20·분당 4)
AI_TAG_GEMINI_DAILY_LIMIT = config("AI_TAG_GEMINI_DAILY_LIMIT", default=20, cast=int)
AI_TAG_GEMINI_RPM = config("AI_TAG_GEMINI_RPM", default=4, cast=int)

# 장소/유저 텍스트 임베딩 (P1.5, provider 토글: ollama | gemini). 1024D 고정(PlaceFeature.content_vector).
EMBEDDING_PROVIDER = config("EMBEDDING_PROVIDER", default="ollama")
OLLAMA_EMBED_MODEL = config("OLLAMA_EMBED_MODEL", default="bge-m3")
GEMINI_EMBED_MODEL = config("GEMINI_EMBED_MODEL", default="gemini-embedding-001")


# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django.log"),
            "when": "midnight",
            "backupCount": 7,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "celery_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "celery.log"),
            "when": "midnight",
            "backupCount": 7,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# Kakao OAuth Settings
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")
KAKAO_JS_KEY = os.getenv("KAKAO_JS_KEY", "")
KAKAO_REST_API_KEY = os.getenv("KAKAO_CLIENT_ID", "")

# Frontend URL
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# AWS 설정
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="ap-northeast-2")
