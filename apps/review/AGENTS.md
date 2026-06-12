# Review App — Agent Guidance

Scoped guidance for `apps/review/`. Follow the project-level `AGENTS.md` for all general rules.

---

## Overview

Handles review CRUD for travel destinations. One review per user per place. Review images are uploaded directly to S3 by the client via a presigned URL; the backend only stores the resulting `image_url`. A review can optionally be linked to one of the author's own `Route`s that includes the reviewed place ("I visited this place as part of this trip").

---

## Model Constraints

- `unique_together = ("user", "place")` — enforce at service layer before DB insert, not only at DB level
- `ordering = ["-id"]` — PK ordering preferred over `-created_at` for index efficiency
- `image_url` is set directly at creation time from the client-supplied presigned `img_url` (nullable)
- `route` is a nullable FK to `route.Route` (`on_delete=SET_NULL`, `related_name="reviews"`) — optional, manual opt-in link

---

## Business Rules

- `Place.rating_avg` and `Place.rating_count` must be recalculated on every review create, update, and delete
- `_update_place_rating()` must always be called inside a `@transaction.atomic` block
- `select_for_update()` on Place prevents race conditions during concurrent review writes
- Allowed updatable fields: `rating`, `content`, `image_url` — enforced via `_REVIEW_UPDATABLE_FIELDS`
- `route_id` is handled separately from `_REVIEW_UPDATABLE_FIELDS` (requires FK lookup/validation via `_get_review_route()`)

---

## Route Linking

- Linking is **manual, opt-in** — never auto-attached. The user chooses an existing route when creating/editing a review.
- `route_id` (optional) is accepted on both create and update requests.
- `_get_review_route(user, place_id, route_id)` validates:
  - `route_id=None` → returns `None` (no link / unlink)
  - Route must belong to the requesting user (`Route.objects.get(pk=route_id, user_id=user.pk)`) — otherwise `RouteNotFound` (404)
  - Route must include the reviewed place via `route.days.filter(day_places__place_id=place_id).exists()` — otherwise `RouteNotIncluded` (400)
- On update, passing `route_id: null` clears the link (`SET_NULL`); omitting `route_id` leaves the existing link unchanged.
- Responses expose the linked route via `ReviewRouteSerializer` (`route_id`, `title`), or `null` if unlinked.

---

## Image Upload (Presigned URL)

- `ReviewImagePresignedUrlView` (`reviews/presigned-url`) uses `apps.core.presigned_url.views.PresignedUrlView` (`path="reviews"`) to issue a presigned S3 PUT URL + final `img_url`
- Client flow: request presigned URL → upload image directly to S3 → pass the returned `img_url` as `image_url` when creating/updating a review
- `image_url` is validated in the serializer via `_validate_image_url()` — must start with `https://{AWS_STORAGE_BUCKET_NAME}`
- Requires AWS credentials in `.env.local`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`

---

## API Endpoints

| Method | URL | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/places/{place_id}/reviews` | ❌ | Returns `count`, `avg_rating`, paginated `results` |
| POST | `/api/v1/places/{place_id}/reviews` | ✅ | JSON body; `image_url`, `route_id` fields optional |
| POST | `/api/v1/reviews/presigned-url` | ✅ | Issues S3 presigned upload URL + `img_url` |
| PATCH | `/api/v1/reviews/{review_id}` | ✅ | At least one field required; `route_id: null` unlinks the route |
| DELETE | `/api/v1/reviews/{review_id}` | ✅ | Triggers rating recalculation |

---

## Testing

- `PlaceFactory` requires `content_id` and `content_type_id` fields (added after place model update)
- Use `override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")` for `image_url` domain validation tests
- Pass `image_url` as a plain string in the request body — no multipart/file fixtures needed
- No `RouteDay`/`RouteDayPlace` factories exist — build a route that includes a place via `RouteFactory` (from `apps.route.tests.factories`) plus direct `RouteDay.objects.create()` / `RouteDayPlace.objects.create()` calls (see `_create_route_with_place()` in `test_reviews.py`)
- Use `format="json"` when sending `route_id: null` in a PATCH body — the default multipart test format mishandles `None`

---

## Do Not

- Do not call `_update_place_rating()` outside a `@transaction.atomic` block
- Do not put S3 upload logic in views or services — presigned URL issuance belongs in `apps.core.presigned_url`
- Do not validate `image_url` domain in services — serializer handles it via `_validate_image_url()`
- Do not use `Review.objects.create()` directly in test bodies — use `ReviewFactory`
- Do not auto-link a route to a review — linking must always be an explicit `route_id` from the client
- Do not skip the "route includes this place" check (`RouteNotIncluded`) — a review's route must contain the reviewed place
