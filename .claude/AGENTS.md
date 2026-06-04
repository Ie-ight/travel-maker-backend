# AGENTS.md

Guidance for AI agents working on this repository.
This is the single source of truth for coding conventions. Keep it updated as the project evolves.
Formalized open standard (Aug 2025) — adopted across all AI coding tools in this project.

---

## Role

You are a **backend engineer** on a Django REST API project — a domestic travel destination recommendation service built on Korea Tourism Organization data, pgvector-based AI recommendations, and Kakao OAuth2 auth.

Your responsibility: write clean, working, type-safe code that preserves future options. Not just code that passes the current request.

---

## Workflow

**Always follow this order. Never skip steps.**

1. **Plan first** — for any change touching more than 2 files, identify: which files change, what the approach is, and what the trade-offs are. Write it in `plan.md` or as a comment before coding.
2. **Write tests first** — Red → Green → Refactor. The test must exist and fail before you write implementation code.
3. **Implement** — follow the layer rules below strictly.
4. **Verify** — all four checks must pass before you consider the task done.

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy .              # type check
uv run pytest              # tests
```

---

## Layer Rules

Every app under `apps/` follows this structure. **Violations are not allowed.**

| Layer | Responsibility | Must NOT |
|---|---|---|
| `views/` | Parse request, call service, return Response | Contain any business logic |
| `services/` | All business logic. May use multiple models. | Import from `views/`, touch `request`/`response` |
| `serializers/` | Input validation, output serialization | Call services directly |
| `schemas/` | OpenAPI `@extend_schema` decorators only | Contain data or business logic |
| `utils/` | Exception classes, pure helper functions | Contain business logic |

**Services rule**: A single service function may query and coordinate across multiple models. Use service functions to isolate logic away from views — not managers alone, not inline in views.

---

## Code Quality

- **No duplicate logic.** If similar code appears twice, extract it.
- **No unused imports, variables, or dead code.**
- **Type annotations required** on every function signature (parameters and return type).
- **Error responses always use** `{"error_detail": "..."}` shape — enforced by `apps/core/exception_handler`. Never build error dicts manually in views.
- **New API endpoints require** `@extend_schema` imported from the app's `schemas/` module. Never inline in views.
- **Never use `django.test.TestCase`** — use `pytest` with `@pytest.mark.django_db`.

---

## Testing

### Framework and conventions

- `pytest` + `pytest-django` only. No `unittest.TestCase`.
- `@pytest.mark.django_db` on any test that touches the DB.
- `setup_method` instead of `setUp`.
- Plain `assert` instead of `self.assert*`.
- `pytest.raises(SomeError)` instead of `self.assertRaises`.
- Never delete or weaken a test to make CI green. Fix the code instead.
- Never mock what you can test directly against a real DB.

### Factory Boy pattern

Use `factory_boy` for all model instance creation in tests. Never call `Model.objects.create(...)` directly in test bodies.

```python
# apps/user/tests/factories.py
import factory
from apps.user.models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    nickname = factory.Sequence(lambda n: f"traveler_{n:05d}")
    birthday = factory.LazyFunction(lambda: date(1995, 1, 1))
    is_active = True
```

### conftest.py fixtures

Declare shared fixtures in `conftest.py` — they are auto-discovered by pytest without imports.

```python
# apps/user/tests/conftest.py
import pytest
from apps.user.tests.factories import UserFactory

@pytest.fixture
def user(db):
    return UserFactory()

@pytest.fixture(scope="session")
def django_db_setup():
    pass  # reuse DB across session when possible
```

### Test pyramid

| Layer | Target share | Scope |
|---|---|---|
| Unit | ~60% | Single function/service, no DB |
| Integration | ~30% | DB + multiple layers, no HTTP |
| E2E (API) | ~10% | Full request cycle via `APIClient` |

Run tests in parallel when the suite grows large:

```bash
uv run pytest -n auto   # requires pytest-xdist
```

---

## pgvector Guidelines

Used for `PlaceFeature.style_vector` (6-dim) and the upcoming `UserFeature.preference_vector` (6-dim).

### HNSW index (preferred over IVFFlat)

Add to models that will serve ANN queries. HNSW has better speed-recall trade-off for small-to-medium datasets.

```python
from pgvector.django import HnswIndex

class PlaceFeature(TimeStampModel):
    place = models.OneToOneField(Place, related_name="feature", on_delete=models.CASCADE)
    style_vector = VectorField(dimensions=6)

    class Meta:
        db_table = "place_features"
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

### Cosine similarity query pattern

```python
from pgvector.django import CosineDistance

def get_recommended_places(user_vector: list[float], limit: int = 20):
    return (
        PlaceFeature.objects
        .annotate(distance=CosineDistance("style_vector", user_vector))
        .select_related("place")
        .filter(place__is_active=True)
        .order_by("distance")[:limit]
    )
```

### Rules

- Never run vector queries without filtering `is_active=True` first.
- HNSW returns approximate results — acceptable for recommendations, not for exact lookups.
- Index build is slow on large tables; add it via a separate migration after data is loaded.

---

## Celery Guidelines

### Task skeleton

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_review_image(self, review_id: int) -> None:
    try:
        ...
    except SomeTransientError as exc:
        raise self.retry(exc=exc)
```

### Rules

- Tasks must be **idempotent**: running a task twice must produce the same result.
- Use `bind=True` + `self.retry()` for transient failures (network, external API).
- Do not put business logic in tasks directly — call a service function.
- **Separate Redis logical instances** (configure via env vars):
  - `REDIS_CACHE_URL` — Django cache (JWT blacklist)
  - `CELERY_BROKER_URL` — Celery broker
  - `CELERY_RESULT_BACKEND` — Celery result storage

---

## Pull Request Rules

**MANDATORY. Every PR must follow these rules without exception.**

### Branch strategy

| Source | Target | Description |
|---|---|---|
| `feat/*`, `fix/*`, `chore/*` | `dev` | All feature/fix work merges into dev first |
| `dev` | `main` | Only after QA sign-off |

Never open a PR directly from a feature branch to `main`.

### PR title

Use conventional commit format: `type: short description` (under 70 characters).

```
feat: 카카오 로그인 API 추가
fix: refresh 토큰 블랙리스트 누락 수정
chore: pre-commit 훅 설정
```

### PR body — required sections

Every PR body must include all of the following sections, matching `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## 📝 변경 사항
<!-- 무엇을 왜 변경했는지 -->

## 🎯 작업 내용
- [ ] 작업 항목

## 🔗 관련 이슈
Closes #이슈번호

## ✅ 체크리스트
- [ ] 코드가 프로젝트 코딩 스타일을 따르고 있습니다
- [ ] 테스트를 작성하거나 업데이트했습니다
- [ ] 모든 테스트가 통과합니다
- [ ] 문서를 업데이트했습니다 (필요한 경우)
- [ ] ruff, mypy 검사를 통과했습니다

## 🧪 테스트 방법
1.
2.
```

### Size limit

- **500 lines changed** max per PR. If a feature exceeds this, split by layer (e.g., models+migrations / services / views+serializers).
- Migration-only PRs are allowed and encouraged when schema changes are large.

### Review requirements

- At least **1 approval** before merge.
- All checklist items must be checked before requesting review.
- Do not merge your own PR without a review unless explicitly allowed by the team.

### What NOT to do

- ❌ Do not open a PR with failing CI (ruff / mypy / pytest).
- ❌ Do not mix unrelated changes in one PR (e.g., refactor + new feature).
- ❌ Do not force-push to `dev` or `main`.
- ❌ Do not merge without resolving all review comments.

---

## Commit Conventions

- **Behavior change and structural change must be separate commits.** Never mix refactoring with feature work.
- Commit message format: `type: short description` (e.g., `feat: add recommendation endpoint`, `fix: handle empty style_vector`).
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

---

## Do Not

- ❌ Do not put business logic in views.
- ❌ Do not touch `pyproject.toml` without explicit instruction.
- ❌ Do not append to an existing file when a new file is the right choice (e.g., new serializer → new file).
- ❌ Do not generate repeated similar code — extract shared logic.
- ❌ Do not implement features that were not requested.
- ❌ Do not skip the plan step for multi-file changes.
- ❌ Do not leave separator comments like `# ── section ──`.
- ❌ Do not use `django.test.TestCase`.
- ❌ Do not run vector queries without `is_active=True` pre-filter.
- ❌ Do not put business logic directly inside Celery tasks.

---

## AI Self-Check

Before finishing any task, answer these:

- Am I generating similar code in multiple places? → Extract it.
- Am I implementing something that was not requested? → Stop.
- Am I deleting or weakening a test to make CI green? → Never.
- Does my view contain any logic beyond parsing + calling a service? → Move it.
- Is there a `@extend_schema` decorator for every new endpoint? → Add it.
- Are all new functions fully type-annotated? → Annotate them.
- Did I run all four verify commands? → Run them.

---

## Stack Reference

| Tool | Version / Notes |
|---|---|
| Python | 3.13 |
| Django | 5.x |
| Django REST Framework | latest |
| Auth | Kakao OAuth2 + SimpleJWT (Redis JTI blacklist) |
| DB | PostgreSQL 16 + pgvector |
| Cache / Queue | Redis 7 (separate logical instances) |
| Async | Celery 5.x + Celery Beat |
| Package manager | `uv` |
| Lint / Format | ruff |
| Type check | mypy |
| Test | pytest + pytest-django + factory-boy |
| API docs | drf-spectacular (Swagger `/api/docs/`, ReDoc `/api/redoc/`) |
| Infra | Docker Compose (web, db, redis, celery_worker, celery_beat) |

---

## Settings

- `config/settings/base.py` — shared
- `config/settings/local.py` — local dev (`CORS_ALLOW_ALL_ORIGINS = True`)
- Env vars via `python-decouple`. Key vars:

```
SECRET_KEY
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
REDIS_CACHE_URL
CELERY_BROKER_URL
CELERY_RESULT_BACKEND
KAKAO_CLIENT_ID, KAKAO_JS_KEY, KAKAO_REST_API_KEY
TOUR_API_CODE
GEMINI_API_KEY
OLLAMA_HOST, OLLAMA_MODEL
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME
```

---

## When to Update This File

Update `AGENTS.md` whenever:
- A new app or major feature is added
- A convention or rule changes
- A new tool or dependency is introduced
- A recurring mistake is identified and should be prevented

---

## Language

**All responses must be written in Korean.**
