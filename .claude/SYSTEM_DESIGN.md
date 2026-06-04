# SYSTEM_DESIGN.md

Backend design document for **TravelMaker**, a domestic travel destination recommendation service.
Read this document before implementing anything. Update it when new features are added.

---

## Service Overview

A service that recommends domestic travel destinations based on Korea Tourism Organization (한국관광공사) Tour API data. Provides place exploration, bookmarks, reviews, map integration, and AI-based tag/preference vectors with pgvector cosine similarity recommendations.

---

## Architecture

### Overall Structure

```
Client (Next.js)
    │
    ▼
Django REST API (Gunicorn)
    ├── apps/user        # Auth (Kakao OAuth2), profile, follow
    ├── apps/place       # Place data, map API, tags, recommendation
    ├── apps/review      # Reviews
    └── apps/bookmark    # Bookmarks
    │
    ├── PostgreSQL 16 + pgvector   # Primary DB + HNSW vector search
    ├── Redis 7                     # JWT blacklist cache / Celery broker / Celery results
    └── Celery 5 Worker/Beat        # Async tasks, incremental sync scheduling
```

### Redis Instance Separation

Three logical Redis databases to prevent cache eviction from interfering with the task queue:

| Logical DB | Env var | Purpose |
|---|---|---|
| `db=0` | `REDIS_CACHE_URL` | Django cache — JWT JTI blacklist |
| `db=1` | `CELERY_BROKER_URL` | Celery task broker |
| `db=2` | `CELERY_RESULT_BACKEND` | Celery task result storage |

### Layer Structure (per app)

```
views/        HTTP entry point. Parse request → call service → return response only.
services/     All business logic. May coordinate across multiple models. No HTTP.
serializers/  Input validation + output serialization.
schemas/      drf-spectacular @extend_schema decorators. Docs only.
utils/        Exception classes, pure helper functions.
```

---

## Per-App Design

### apps/core
- `TimeStampModel`: abstract base model with `created_at` / `updated_at`
- `custom_exception_handler`: normalizes all API errors to `{"error_detail": "..."}` shape
- Shared exceptions: `Conflict`, `NotFound`

### apps/user

**Models**
```
User (AbstractBaseUser + TimeStampModel)
  - email (unique)
  - nickname
  - bio, gender, birthday
  - profile_img_url
  - tags (M2M → place.Tag)   # interest tags shown on profile
  - is_active, deleted_at    # soft delete
  - is_staff, role (USER | ADMIN)

SocialUser (TimeStampModel)
  - user (FK → User)
  - provider ("kakao")
  - provider_id

Follow
  - follower (FK → User)
  - following (FK → User)
  - unique_together: (follower, following)

UserFeature [UPCOMING]       # preference vector for recommendation
  - user (OneToOne → User)
  - preference_vector VECTOR(6)
    axis order matches PlaceFeature.style_vector:
    [activity, planning, sociability, space_orientation,
     experience_orientation, spending_style]
  - created_at, updated_at
```

**Auth flow**
```
[Frontend-driven]
POST /api/v1/auth/kakao/login
  Kakao auth code → backend → Kakao API → find/create user
  Response: body { access_token } + Set-Cookie: refresh_token (HttpOnly, 7 days)

[Backend callback]
GET /api/v1/auth/kakao/callback
  Kakao redirect → backend processing → 302 redirect to frontend (query params)
```

**Token management**
- Access Token: response body, 60 min expiry
- Refresh Token: HttpOnly cookie, 7 days, Redis JTI blacklist
- Reissue: `POST /api/v1/auth/token/refresh`
- Withdrawal: soft delete (`is_active=False`, `deleted_at=now()`), 14-day recovery window

### apps/place

**Models**
```
Place (TimeStampModel)
  - place_name, latitude, longitude
  - description (AI tagging input — Tour API overview)
  - content_id (Tour API unique ID, unique, db_index)
  - content_type_id (12:attraction, 14:cultural facility, 28:leisure,
                     32:accommodation, 38:shopping, 39:restaurant)
  - address_primary, address_detail, tel, homepage, zipcode
  - lcls_systm1/2/3 (Korea Tourism Organization classification codes)
  - rating_avg, rating_count
  - is_active (soft delete)
  - tags (M2M → Tag)

PlaceImage
  - place (FK), image_url, thumbnail_url
  - is_main, order
  - unique_together: (place, image_url)

PlaceInfo (1:1 → Place)
  - operating_hours, closed_days, parking (bool nullable)
  - admission_fee, spend_time, discount_info, accom_count
  - pet, baby_carriage, credit_card (BooleanField nullable)

PlaceFeature (1:1 → Place)
  - style_vector VECTOR(6)
  - HNSW index (vector_cosine_ops, m=16, ef_construction=64)
  Vector axis order:
    [0] activity        (active ↔ healing)
    [1] planning        (planned ↔ spontaneous)
    [2] sociability     (solo ↔ group)
    [3] space           (nature ↔ urban)
    [4] experience      (cultural ↔ hands-on)
    [5] spending        (budget ↔ luxury)
  Each value: 0.0~1.0, 0.5 = neutral

Tag
  - tag_type: travel style | detailed theme | companion | region | convenience
  - tag_name (unique)
```

**Recommendation Pipeline**

Three-stage approach inspired by industry patterns (content-based → vector ANN → fallback):

```
Stage 1 — Pre-filter
  WHERE place.is_active = True
  AND   (optional) tag match
  AND   (optional) region tag match

Stage 2 — ANN via HNSW
  ORDER BY CosineDistance(style_vector, user_preference_vector)
  LIMIT 20
  (requires UserFeature to exist for the requesting user)

Stage 3 — Fallback (anonymous or no preference vector set)
  ORDER BY rating_avg DESC, bookmark_count DESC
```

**Data collection pipeline** (management commands)
```
sync_lcls_codes  → Save Tour API classification code names to lcls_codes.json
seed_tags        → Seed tag candidates into DB
sync_places      → Collect places (list → detail → images → operating info)
assign_tags      → Deterministically assign region/convenience tags
ai_tag           → Generate AI tags + style_vector (Gemini or Ollama)
```

**Map API**
```
GET /api/v1/places/map              → Full place coordinate list (for markers)
GET /api/v1/places/map/route        → My location → place route (Kakao Mobility proxy)
GET /api/v1/places/config/kakao     → Return Kakao JS key
```

### apps/review
```
Review
  - user (FK), place (FK)
  - content, rating (1~5), image_url
  - unique_together: (user, place)   # one review per place per user
```

Image processing runs asynchronously via a Celery task. Planned: replace URL-direct storage with S3 presigned URL upload.

### apps/bookmark
```
Bookmark
  - user (FK), place (FK)
  - unique_together: (user, place)
```

---

## API Conventions

### Error responses
All errors use the shape below. No exceptions.
```json
{"error_detail": "message"}
```

### Authentication
- `Authorization: Bearer {access_token}` header
- All endpoints not marked `AllowAny` require JWT authentication

### Pagination
- `PageNumberPagination`, default `page_size=8`, max 100
- Response: `{ count, next, previous, results }`

### API documentation
- Swagger: `/api/docs/`
- ReDoc: `/api/redoc/`
- `@extend_schema` required on all view methods, imported from the app's `schemas/` module

---

## External Service Integrations

| Service | Purpose | Env var |
|---------|---------|---------|
| Kakao OAuth2 | Social login | `KAKAO_CLIENT_ID` |
| Kakao Maps JS SDK | Frontend map rendering | `KAKAO_JS_KEY` |
| Kakao Mobility API | Route query backend proxy | `KAKAO_CLIENT_ID` (REST) |
| Korea Tourism Organization KorService2 | Place data collection | `TOUR_API_CODE` |
| Gemini API | AI tagging (production) | `GEMINI_API_KEY` |
| Ollama (local) | AI tagging (development) | `OLLAMA_HOST`, `OLLAMA_MODEL` |
| AWS S3 | Review image storage (planned) | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME` |

---

## Settings Structure

```
config/settings/
  base.py     # shared config
  local.py    # local dev (CORS_ALLOW_ALL_ORIGINS=True)
  prod.py     # production
```

Environment variables loaded via `python-decouple`'s `config()`. `.env` file location: `envs/.env.local`

---

## Infrastructure

```yaml
# docker-compose.yml services
web:           Django (Gunicorn), port 8000
db:            PostgreSQL 16 + pgvector, port 5432
redis:         Redis 7, port 6379 (logical DBs 0/1/2 for cache/broker/results)
celery_worker: async task processing (review image, AI tagging)
celery_beat:   scheduled tasks — incremental place sync (monthly)
```

---

## Open / Planned Work

- [ ] `UserFeature` model + preference survey API (`POST /api/v1/users/me/survey`)
- [ ] HNSW index migration on `PlaceFeature.style_vector`
- [ ] pgvector cosine similarity recommendation endpoint (`GET /api/v1/places/recommend`)
- [ ] User interest tags API (`GET/PUT /api/v1/users/me/tags`)
- [ ] Follow/unfollow API + follower/following list
- [ ] Follow feed API (`GET /api/v1/feed`)
- [ ] Review image S3 presigned URL upload (replace URL-direct storage)
- [ ] Incremental sync Celery Beat schedule (`sync_places --sync`, monthly)

---

## Language

**All responses must be written in Korean.**
