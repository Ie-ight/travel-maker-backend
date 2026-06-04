# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync --all-extras

# Run all tests
uv run pytest

# Run a single test file
uv run pytest apps/user/tests/test_auth.py

# Run a single test class or method
uv run pytest apps/user/tests/test_auth.py::KakaoLoginViewTest::test_기존_유저_로그인_200

# Run tests with coverage
uv run pytest --cov --cov-report=term-missing

# Run tests in parallel (install pytest-xdist first)
uv run pytest -n auto

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy .

# Run dev server (requires DB and Redis)
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py runserver

# Apply migrations
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py migrate
```

CI requires both PostgreSQL (port 5432) and Redis (port 6379). Tests use `config.settings.local` as `DJANGO_SETTINGS_MODULE`.

---

## Architecture

### Layer structure (per app)

Each app under `apps/` follows a strict layered pattern:

```
views/       → HTTP only: parse request, call service, return Response
services/    → All business logic. May coordinate across multiple models.
serializers/ → Input validation and output serialization
schemas/     → drf_spectacular @extend_schema decorators (OpenAPI docs only)
utils/       → Exception classes and helpers
```

Views must not contain business logic. Services must not touch HTTP. This separation is enforced by convention and checked in code review.

### Apps

- **`apps/core`**: `TimeStampModel` (abstract base with `created_at`/`updated_at`), custom exception handler, shared `Conflict`/`NotFound` exception classes.
- **`apps/user`**: Custom `User` model (`AbstractBaseUser` + `TimeStampModel`). `SocialUser` links users to OAuth providers (Kakao). `Follow` model for follow graph. Upcoming: `UserFeature` (1:1 User, `preference_vector VECTOR(6)`).
- **`apps/place`**: `Place`, `PlaceImage`, `PlaceInfo`, `PlaceFeature` (style_vector), `Tag` models. `PlaceFeature.style_vector` is indexed with HNSW (`vector_cosine_ops`) for ANN recommendation queries.
- **`apps/review`**: `Review` — one per user per place (`unique_together`). Image upload via Celery async task.
- **`apps/bookmark`**: `Bookmark` — unique per user+place.

### Auth flow

Kakao OAuth2 only. Two entry points:
- **Frontend-driven** (`POST /api/v1/auth/kakao/login`): frontend exchanges auth code → backend calls Kakao API → returns tokens.
- **Backend-driven callback** (`GET /api/v1/auth/kakao/callback`): Kakao redirects here → backend processes → 302 redirect to frontend with result in query params.

Token storage:
- **Access token**: response body (`{"access_token": "..."}`)
- **Refresh token**: `HttpOnly` cookie (`refresh_token`), 7-day TTL

Token blacklisting uses **Redis cache** (not SimpleJWT's DB blacklist). On logout/withdrawal, the refresh token's JTI is stored in Redis with TTL matching token expiry. `KakaoAuthService.is_jti_blacklisted()` fails open (returns `False`) on cache errors.

Withdrawal is a **soft delete**: `is_active=False` + `deleted_at=now()`. Recoverable within 14 days via `POST /api/v1/auth/recovery`.

### Recommendation pipeline

Three-stage approach (content-based → vector → fallback):

1. **Pre-filter**: `is_active=True`, optionally filter by tag IDs or region tag.
2. **ANN query**: `CosineDistance("style_vector", user_preference_vector)` via HNSW index → top-N candidates.
3. **Fallback** (anonymous / no preference vector): order by `rating_avg DESC`, `bookmark_count DESC`.

### Error response convention

All API errors use `{"error_detail": "..."}` shape. Enforced globally by `apps/core/exception_handler.custom_exception_handler`.

Auth-specific exceptions in `apps/user/utils/auth_exceptions.py` inherit from `AuthBaseException`. Views catch these and manually build the response.

---

## Key Patterns

### pgvector cosine similarity query

```python
from pgvector.django import CosineDistance

PlaceFeature.objects
    .annotate(distance=CosineDistance("style_vector", user_vector))
    .select_related("place")
    .filter(place__is_active=True)
    .order_by("distance")[:20]
```

### HNSW index on a vector field

```python
from pgvector.django import HnswIndex, VectorField

class Meta:
    indexes = [
        HnswIndex(
            name="place_style_vector_hnsw",
            fields=["style_vector"],
            m=16,
            ef_construction=64,
            opclasses=["vector_cosine_ops"],
        )
    ]
```

### Celery task (idempotent, retryable)

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def my_task(self, record_id: int) -> None:
    try:
        some_service.process(record_id)
    except TransientError as exc:
        raise self.retry(exc=exc)
```

### factory-boy for tests

```python
import factory
from apps.place.models import Place

class PlaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Place

    place_name = factory.Sequence(lambda n: f"Place {n}")
    content_id = factory.Sequence(lambda n: n + 1000)
    content_type_id = 14
    is_active = True
```

---

## Settings

- `config/settings/base.py`: shared config
- `config/settings/local.py`: local dev overrides (`CORS_ALLOW_ALL_ORIGINS = True`)
- Environment variables loaded via `python-decouple` (`config()` calls)

Key env vars:

```
SECRET_KEY
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
REDIS_CACHE_URL              # Django cache (JWT blacklist)
CELERY_BROKER_URL            # Celery broker (separate Redis logical DB)
CELERY_RESULT_BACKEND        # Celery result storage
KAKAO_CLIENT_ID, KAKAO_JS_KEY, KAKAO_REST_API_KEY, KAKAO_REDIRECT_URI
FRONTEND_URL
TOUR_API_CODE
GEMINI_API_KEY
OLLAMA_HOST, OLLAMA_MODEL
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME
```

---

## API documentation

Swagger UI: `/api/docs/` · ReDoc: `/api/redoc/`

Each view method is decorated with `@extend_schema(...)` imported from the app's `schemas/` module. Add schema decorators there, not inline in views.
