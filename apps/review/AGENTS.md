# Review App — Agent Guidance

Scoped guidance for `apps/review/`. Follow the project-level `AGENTS.md` for all general rules.

---

## Overview

Handles review CRUD for travel destinations. One review per user per place. Image upload is processed asynchronously via Celery after the review is created.

---

## Model Constraints

- `unique_together = ("user", "place")` — enforce at service layer before DB insert, not only at DB level
- `ordering = ["-id"]` — PK ordering preferred over `-created_at` for index efficiency
- `image_url` is `null` immediately after creation; updated by Celery task after S3 upload completes

---

## Business Rules

- `Place.rating_avg` and `Place.rating_count` must be recalculated on every review create, update, and delete
- `_update_place_rating()` must always be called inside a `@transaction.atomic` block
- `select_for_update()` on Place prevents race conditions during concurrent review writes
- Allowed updatable fields: `rating`, `content`, `image_url` — enforced via `_REVIEW_UPDATABLE_FIELDS`

---

## Image Upload (Celery)

- Task: `upload_review_image` in `tasks.py`
  1. Compress with Pillow to ≤10MB (JPEG quality loop; PNG uses lossless)
  2. Upload to S3 via `_get_s3_client()` (lazy singleton)
  3. Update `review.image_url` via `filter().update()` — no ORM object load
- On failure: `image_url` remains `null`. No user notification (not in requirements).
- Requires AWS credentials in `.env.local`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`

---

## API Endpoints

| Method | URL | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/places/{place_id}/reviews` | ❌ | Returns `count`, `avg_rating`, paginated `results` |
| POST | `/api/v1/places/{place_id}/reviews` | ✅ | `multipart/form-data`; `image` field optional |
| PATCH | `/api/v1/reviews/{review_id}` | ✅ | At least one field required |
| DELETE | `/api/v1/reviews/{review_id}` | ✅ | Triggers rating recalculation |

---

## Testing

- Mock Celery task in tests: `patch("apps.review.services.review_services.upload_review_image")`
- `PlaceFactory` requires `content_id` and `content_type_id` fields (added after place model update)
- Create test image files using `PILImage` + `BytesIO`
- Use `override_settings(AWS_STORAGE_BUCKET_NAME="test-bucket")` for `image_url` domain validation tests

---

## Do Not

- Do not call `_update_place_rating()` outside a `@transaction.atomic` block
- Do not put S3 upload logic in views or services — it belongs in `tasks.py`
- Do not validate `image_url` domain in services — serializer handles it via `validate_image_url()`
- Do not use `Review.objects.create()` directly in test bodies — use `ReviewFactory`
