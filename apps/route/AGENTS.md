# Route App — Agent Guidance

Scoped guidance for `apps/route/`. Follow the project-level `AGENTS.md` for all general rules.

---

## Overview

Handles travel itinerary (route) CRUD. A `Route` has 1~5 `RouteDay`s, and each `RouteDay` has 1~5 `RouteDayPlace`s in visiting order — together these drive the map polyline (day_index/order ordering + place coordinates). Also supports likes (`RouteLike`), region/theme tag filtering, latest/popular ordering, and admin force-delete. `apps/review` can optionally link a review back to a `Route` (see `apps/review/AGENTS.md`'s "Route Linking" section).

---

## Model Constraints

- `Route`: `title` max 20 chars, `description` nullable, `region_tag` FK to `Tag` (`SET_NULL`, nullable), `theme_tags` M2M to `Tag`, `start_date`/`end_date`, `like_count` (default 0, `PositiveIntegerField`). `ordering = ["-created_at"]`.
- `RouteDay`: FK `route` (`related_name="days"`), `day_index` (`PositiveSmallIntegerField`, 1~5 via `MinValueValidator`/`MaxValueValidator`), `unique_together = ("route", "day_index")`, `ordering = ["day_index"]`.
- `RouteDayPlace`: FK `route_day` (`related_name="day_places"`), FK `place`, `order` (1~5), `unique_together = ("route_day", "order")`, `ordering = ["order"]`.
- `RouteLike`: `unique_together = ("route", "user")`.

---

## Business Rules

- `start_date <= end_date`, and the span is capped at 4박5일 (`(end_date - start_date).days + 1 <= 5`) — enforced in `RouteCreateSerializer.validate()`.
- `_validate_days()`: `day_index` must fall within `1..total_days` (computed from the date range), no duplicate `day_index` values across `days`, and each day's `place_ids` must contain 1~5 entries.
- `_validate_region_tag()` / `_validate_place_ids()` pre-check FK existence for `region_tag_id` and every `place_id` so invalid IDs raise `RouteValidationError` (400) instead of an `IntegrityError` (500).
- On update, if `days` is provided, ALL existing `RouteDay`/`RouteDayPlace` rows are deleted and recreated from scratch (`route.days.all().delete()` + `_create_days()`) — there is no partial/diff-based day update.
- `_create_days()` assigns `order` to each place based on its position in `place_ids` (1-indexed), preserving map line order.
- Only the route owner can update/delete (`RouteForbidden`, 403). `AdminRouteDetailView` (routed under `apps/user/urls/admin_urls.py`, `IsAdminRole`) can force-delete any route.
- Liking is idempotent-checked: `RouteAlreadyLiked` (409) if already liked, `RouteLikeNotFound` (404) on unlike if no like exists.
- `like_count` is always updated via `Route.objects.filter(pk=route_id).update(like_count=F("like_count") + 1 / - 1)` — never via instance `.save()` — to avoid race conditions on concurrent likes.
- Create/update responses (`RouteCreateResponseSerializer`/`RouteUpdateResponseSerializer`) include a `days` field (`RouteDayDetailSerializer`, same shape as the detail view: `day_index` + `places[]` with `place_id`/`place_name`/`latitude`/`longitude`/`image_url`) so the frontend can render the map immediately without a follow-up `GET /routes/{id}`. The views re-fetch the route via `get_route_detail()` after create/update to get this prefetched.

---

## Query Optimization

- `_get_route_queryset()` is the shared base for list/detail/user-routes/liked-routes:
  - `select_related("region_tag")` — avoids FK N+1.
  - `prefetch_related("theme_tags", Prefetch("days", ... prefetch "day_places" -> select_related("place") -> prefetch "place__images"))` — nested prefetch ordered by `day_index`/`order` so the map can draw lines without extra queries.
  - `.annotate(place_count=Count("days__day_places", distinct=True))` — total place count computed in DB.
- `get_route_detail()` uses the same nested prefetch directly (no list pagination).

---

## API Endpoints

| Method | URL | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/routes` | ❌ | Paginated (`RoutePagination`, page_size=10, max 50). `region_tag_id`, `theme_tag_ids` (repeatable or comma-separated, AND filter), `ordering=latest\|popular` |
| POST | `/api/v1/routes` | ✅ | `days` required, 1~5 days, 1~5 `place_ids` each, max 4박5일 |
| GET | `/api/v1/routes/{route_id}` | ❌ | `RouteDetailSerializer` — includes per-day places with coordinates/images |
| PATCH | `/api/v1/routes/{route_id}` | ✅ | Owner only (`RouteForbidden`); `days` if present replaces all days/places |
| DELETE | `/api/v1/routes/{route_id}` | ✅ | Owner only |
| GET | `/api/v1/users/{nickname}/routes` | ✅ | `RouteMyListSerializer`, paginated |
| GET | `/api/v1/users/routes/likes` | ✅ | Current user's liked routes; route in `urls.py` registered BEFORE `users/<str:nickname>/routes` to avoid path collision |
| POST | `/api/v1/routes/{route_id}/like` | ✅ | 409 if already liked |
| DELETE | `/api/v1/routes/{route_id}/like` | ✅ | 404 if not liked |
| DELETE | `/api/v1/admin/routes/{route_id}` | ✅ (admin) | `AdminRouteDetailView`, `IsAdminRole`, force-delete |

---

## Testing

- Factories in `apps/route/tests/factories.py`: `UserFactory`, `AdminUserFactory` (`role="ADMIN"`, `is_staff=True`), `TagFactory`, `PlaceFactory`, `RouteFactory`, `RouteLikeFactory`.
- **No `RouteDay`/`RouteDayPlace` factories exist.** Create them via the API payload's `days` field, or manually with `RouteDay.objects.create(route=route, day_index=...)` + `RouteDayPlace.objects.create(route_day=day, place=place, order=...)` (see `_create_route_with_place()` in `apps/review/tests/test_reviews.py` for the manual pattern).
- `_route_payload(tag_id, place_id, **kwargs)` in `test_route.py` builds a default valid create/update payload — extend with `**kwargs` for edge cases (e.g. `title="가" * 21`, `start_date`/`end_date` overrides, duplicate `day_index`).
- Admin endpoint tests use `admin_client` (force-authenticated `AdminUserFactory` user) against `/api/v1/admin/routes/{route.id}`.

---

## Do Not

- Do not partially update `days` — always replace via delete + recreate (`route.days.all().delete()` then `_create_days()`).
- Do not increment/decrement `like_count` via `route.save()` — use `Route.objects.filter(pk=...).update(like_count=F(...) ± 1)`.
- Do not allow non-owners to update/delete a route — raise `RouteForbidden`.
- Do not skip `_validate_region_tag()` / `_validate_place_ids()` before creating `Route`/`RouteDay`/`RouteDayPlace` rows — this converts FK `IntegrityError` (500) into `RouteValidationError` (400).
- Do not register `users/<str:nickname>/routes` before `users/routes/likes` in `urls.py` — the nickname pattern would swallow the literal `/likes` path.
