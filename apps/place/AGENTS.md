# Place Application Developer & Agent Guide

This document provides guidelines and structural overview of the **Place** application (`apps/place/`) for developers and AI coding agents.

---

## 1. Directory Structure

The application is structured as follows:
```text
apps/place/
├── admin.py                 # Django admin registration and customization
├── apps.py                  # AppConfig defining "apps.place"
├── models.py                # Database models (Place, PlaceImage, Tag, PlaceInfo, PlaceFeature)
├── tasks.py                 # Celery background tasks (syncing, AI tagging)
├── urls.py                  # API endpoints routing
├── management/              # Custom management commands
│   └── commands/
│       └── ai_tag.py        # Management command to trigger AI tagging on backlog places
├── schemas/                 # Swagger / OpenAPI documentation decorators using drf-spectacular
├── serializers/             # Django REST Framework serializers
├── services/                # Business logic layer
│   ├── admin_place_service.py
│   ├── ai_tagging.py        # LLM integration (Gemini/Ollama) and 6D vector tagging
│   ├── lcls_codes.py        # Category code mappings for Tour API classification
│   ├── map_api_service.py   # Kakao Mobility API client for routing and mapping
│   ├── place_info_mapping.py# Field configurations for detailed operation specs
│   ├── place_services.py    # Place detail / list retrieval logic
│   ├── place_sync.py        # Sync orchestrator parsing Tour API payloads
│   ├── sort_algorithm_service.py # pgvector similarity-based recommendation logic
│   ├── tag_seeds.py         # Static categories/tag lists
│   ├── tagging.py           # Standard deterministic tagging rules
│   └── tour_api.py          # HTTP Client wrapper for KTO Tour API
├── views/                   # View layer (API controllers)
│   ├── admin_place_views.py
│   ├── config_views.py      # Config endpoints (e.g. Kakao configuration)
│   ├── map_api_views.py     # Map and Routing views
│   ├── place_views.py       # Search, Filter, list and details views
│   ├── sort_algorithm_views.py # Recommendation view
│   └── tag_views.py         # Tag listing view
└── tests/                   # Test suite using pytest-django
    ├── conftest.py          # Pytest shared fixtures
    ├── factories.py         # FactoryBoy declarations for models
    └── test_*.py            # Tests for API, syncing, tagging, and services
```

---

## 2. Data Models

The domain architecture revolves around [models.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/models.py):

### [Place](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/models.py#L7)
The core entity representing a travel destination.
* Syncs with the Korea Tourism Organisation (KTO) Tour API using `content_id` and `content_type_id`.
* Soft-deleted destinations are marked with `is_active=False` and excluded from lists/details.
* Includes partial indexes (`place_active_rating_idx` and `place_active_review_idx`) for accelerating searches and default sorting.

### [PlaceImage](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/models.py#L54)
Manages the destination's media.
* Has an ordering constraint to dictate carousel display sequence.
* Relies on the `is_main` flag for the list page's representative thumbnail.

### [Tag](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/models.py#L70)
Provides descriptive tags.
* Contains `tag_name` (unique) and `tag_type` (e.g., "분위기", "특징").

### [PlaceInfo](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/models.py#L79)
A `OneToOneField` extension to `Place` capturing operation metrics:
* Parking availability, stroller support, credit card support, pet friendliness, admission fees, and operating hours.

### [PlaceFeature](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/models.py#L100)
A `OneToOneField` extension to `Place` containing a 6-dimensional pgvector (`style_vector`):
* Accelerated via `HnswIndex` with `vector_cosine_ops` to enable cosine-distance similarity recommendations.

---

## 3. Core Business Logic

### A. Tour API Synchronization
* **Client**: [tour_api.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/services/tour_api.py) handles HTTP requests, key rotations, and retry backoff.
* **Orchestrator**: [place_sync.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/services/place_sync.py) normalizes KTO Tour API payloads (e.g., parsing telephone numbers, extracting single URLs from HTML snippets, cleaning HTML line breaks from operation fields).
* **Tagging**: Deterministic tags based on Tour API category codes are applied in [tagging.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/services/tagging.py).

### B. AI Tagging & Vector Profiling
* [ai_tagging.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/services/ai_tagging.py) processes missing place profiles via LLMs (Gemini API or local Ollama).
* Generates JSON structures matching:
  `{"tags": {"여행 스타일": [...], "세부 테마": [...], "동행": [...]}, "style_vector": [v1, v2, v3, v4, v5, v6], "reason": "..."}`
* Maps destinations across **6 Style Axes** (normalized between `0.000` to `1.000`):
  1. Activity (활동성): Activity-driven vs Healing-driven
  2. Planning (계획성): Planning-heavy vs Spontaneous
  3. Sociality (사교성): Solo vs Group
  4. Space Orientation (공간지향): Nature vs City
  5. Experience Orientation (경험지향): Culture vs Experiential
  6. Consumption Style (소비스타일): Cost-effective vs Luxury

### C. Recommendation & Vector Search
* Implemented in [sort_algorithm_service.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/services/sort_algorithm_service.py).
* Computes vector distances relative to user personality vectors fetched from `UserTestResult`.
* **HNSW Scanning Optimization**: When combining the `HnswIndex` cosine distance sorting with Django ORM filters (such as tag selections), under-recall is prevented by configuring PostgreSQL's iterative scan behavior:
  ```python
  with transaction.atomic():
      with connection.cursor() as cursor:
          cursor.execute("SET LOCAL hnsw.iterative_scan = strict_order")
  ```
* Fallback to popular recommendations (cached for 5 minutes) is provided for unauthenticated users or those without personality tests.

### D. Map Routing
* [map_api_service.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/services/map_api_service.py) utilizes the Kakao Mobility API to acquire optimal routes from the user's location to the target destination.

---

## 4. Scheduled Tasks

In production environments, background jobs are scheduled via Celery beat in [tasks.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/tasks.py):
* `sync_incremental_task`: Executes monthly to check for changed/new destinations, soft-deactivating those marked with `showflag=0`.
* `ai_tag_missing_task`: Executes daily to catch up on untagged places using the Gemini API, governed by rate limiting parameters (`AI_TAG_GEMINI_DAILY_LIMIT` & `AI_TAG_GEMINI_RPM`).

---

## 5. Development Guidelines & Rules

### ⚠️ Strict Type Hinting Constraints
**DO NOT import the `typing` module (`import typing` or `from typing import ...`).**
Instead, enforce modern Python type-hinting conventions:
1. **Built-in Collections**: Use standard collection types directly for generics:
   * Use `list[...]` instead of `List[...]`
   * Use `dict[..., ...]` instead of `Dict[..., ...]`
   * Use `tuple[...]` instead of `Tuple[...]`
   * Use `set[...]` instead of `Set[...]`
2. **Union Types (PEP 604)**: Use the pipe operator `|` for optional values or unions:
   * Use `str | None` instead of `Optional[str]`
   * Use `int | float` instead of `Union[int, float]`
3. **Abstract Collections**: Import abstract collections exclusively from `collections.abc` rather than the `typing` module:
   * Use `from collections.abc import Sequence, Iterable, Mapping, Callable`
4. **Exceptions**: Only use alternative syntax if a specific construct is completely unavailable via standard built-ins or `collections.abc` (such as `Any`, which may be imported or represented according to codebase patterns).

### Coding Style & Configuration
* **Code Formatter**: Ruff is used for linting and formatting. Line length limits are set to **120**.
* **Target Version**: Python 3.12 is targeted.
* **Mypy Static Check**: Configured in strict mode. Ensure all methods have correct return type annotations.
* **Permissions**: DRF is configured with `IsAuthenticated` by default. Public endpoints must explicitly declare `permission_classes = [AllowAny]`.
* **Database Queries**: Avoid combining multiple many-to-many aggregations inside a single query to prevent Cartesian product blow-ups. Utilize caching and pre-resolved IDs where appropriate.

---

## 6. Testing Setup

* Launch tests using:
  ```bash
  docker compose -f infrastructure/docker/docker-compose.yml exec web sh -c "uv run pytest apps/place -v"
  ```
* Setup fixtures in [conftest.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/tests/conftest.py) and test mock factories in [factories.py](file:///Users/yimiro/Desktop/travel-maker-backend/apps/place/tests/factories.py) when writing new tests.
* Ensure code coverage is maintained when implementing new features.
