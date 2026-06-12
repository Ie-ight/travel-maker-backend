# Review App — Agent Guidance

Scoped guidance for `apps/review/`. Follow the project-level `AGENTS.md` for all general rules.

---

## Overview

Handles review CRUD for travel destinations. One review per user per place. Review images are uploaded directly to S3 by the client via a presigned URL; the backend only stores the resulting `image_url`.

---

## Model Constraints

- `unique_together = ("user", "place")` — enforce at service layer before DB insert, not only at DB level
- `ordering = ["-id"]` — PK ordering preferred over `-created_at` for index efficiency
- `image_url` is set directly at creation time from the client-supplied presigned `img_url` (nullable)

---

## Business Rules

- `Place.rating_avg` and `Place.rating_count` must be recalculated on every review create, update, and delete
- `_update_place_rating()` must always be called inside a `@transaction.atomic` block
- `select_for_update()` on Place prevents race conditions during concurrent review writes
- Allowed updatable fields: `rating`, `content`, `image_url` — enforced via `_REVIEW_UPDATABLE_FIELDS`

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
| POST | `/api/v1/places/{place_id}/reviews` | ✅ | JSON body; `image_url` field optional |
| POST | `/api/v1/reviews/presigned-url` | ✅ | Issues S3 presigned upload URL + `img_url` |
| PATCH | `/api/v1/reviews/{review_id}` | ✅ | At least one field required |
| DELETE | `/api/v1/reviews/{review_id}` | ✅ | Triggers rating recalculation |

---

## Testing

- `PlaceFactory` requires `content_id` and `content_type_id` fields (added after place model update)
- Use `override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")` for `image_url` domain validation tests
- Pass `image_url` as a plain string in the request body — no multipart/file fixtures needed

---

## Do Not

- Do not call `_update_place_rating()` outside a `@transaction.atomic` block
- Do not put S3 upload logic in views or services — presigned URL issuance belongs in `apps.core.presigned_url`
- Do not validate `image_url` domain in services — serializer handles it via `_validate_image_url()`
- Do not use `Review.objects.create()` directly in test bodies — use `ReviewFactory`
