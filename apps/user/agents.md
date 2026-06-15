## Follow

Handles follow/unfollow between users. Belongs in `apps/user/`.
Create `follow_service.py` separately from `profile_service.py`.

### API Endpoints

| Method | URL | Auth | Notes |
|---|---|---|---|
| POST | `/api/v1/users/{user_id}/follow` | ✅ | Follow a user |
| DELETE | `/api/v1/users/{user_id}/follow` | ✅ | Unfollow a user |
| GET | `/api/v1/users/{user_id}/followers` | ❌ | Follower list — cursor-based pagination |
| GET | `/api/v1/users/{user_id}/following` | ❌ | Following list — cursor-based pagination |
| POST | `/api/v1/users/nickname/check` | ❌ | Nickname duplicate check |

### Model
```python
class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers")
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follow"
        constraints = [models.UniqueConstraint(fields=["follower", "following"], name="unique_follow")]
```

### Response

**POST /api/v1/users/{user_id}/follow**
```json
201: { "detail": "팔로우했습니다." }
```

**DELETE /api/v1/users/{user_id}/follow**

204: No Content

**GET /api/v1/users/{user_id}/followers|following**
```json
{
  "next": "cursor=abc123" | null,
  "previous": "cursor=abc123" | null,
  "results": [
    {
      "user_id": int,
      "nickname": str,
      "profile_img_url": str
    }
  ]
}
```

**POST /api/v1/users/nickname/check**
```json
200: { "detail": "사용가능한 닉네임 입니다." }
400: { "error_detail": { "nickname": ["이 필드는 필수 항목입니다."] } }
409: { "error_detail": "중복된 닉네임이 존재합니다." }
```

---

## Other User Profile (Public)

Handles public profile view for any user. Authentication is not required.
Reuses existing service functions.

### API Endpoints

| Method | URL | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/users/{user_id}` | ❌ | Public profile |
| GET | `/api/v1/users/{user_id}/reviews` | ❌ | Public review list |

### Public vs Private

| Feature | Public | Private (own only) |
|---|---|---|
| 프로필 상단 (닉네임, 한줄소개, 여행타입명, 태그) | ✅ | ✅ |
| 팔로워/팔로잉 수 | ✅ | ✅ |
| 팔로워/팔로잉 목록 | ✅ | ✅ |
| 리뷰 목록 | ✅ | ✅ |
| 북마크 목록 | ❌ | ✅ |
| 프로필 수정 | ❌ | ✅ |
| 여행성향 결과 탭 | ❌ | ✅ |
| 경로 찜목록 | ✅ (추후 공개 예정) | ✅ (추후 구현) |

### My Profile Response (GET /api/v1/users)
```json
200: {
  "id": int,
  "nickname": str,
  "bio": str,
  "email": str,
  "profile_img_url": str,
  "tags": list[{"id": int, "name": str}],
  "bookmark_count": int,
  "review_count": int,
  "follower_count": int,
  "following_count": int,
  "travel_type_name": str | null,
  "created_at": datetime,
  "updated_at": datetime
}
```

### Implementation Note
- Create `PublicUserSerializer` — excludes `email`, `bookmark_count`, `review_count`
- `type_tags` generated from `build_type_tags(type_key)` function in travel_quiz app
- `travel_type_name` from `UserTestResult.travel_type.name` — null if not tested
- `follower_count`, `following_count` from `Follow` model aggregation
- Reuse existing service functions for user/review retrieval
- `permission_classes = [AllowAny]` for public endpoints

### Do Not
- Do not expose `email` in public profile response
- Do not expose `bookmark_count`, `review_count` in public profile

---

## Routes (My Page / Liked)

Moved from `apps/route` per Swagger review feedback. Views live in `apps/user/views/profile_view.py`
(`UserRouteListView`, `UserLikedRoutesView`), but reuse `get_user_routes()`/`get_liked_routes()` and
`RouteMyListSerializer`/`RouteListSerializer` from `apps/route` — no duplicated query logic.

### API Endpoints

| Method | URL | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/users/{nickname}/routes` | ✅ | `RouteMyListSerializer`, paginated; 404 if nickname doesn't exist |
| GET | `/api/v1/users/routes/likes` | ✅ | Current user's liked routes, `RouteListSerializer`, paginated |

### Do Not
- Do not register `users/<str:nickname>/routes` before `users/routes/likes` in `user_urls.py` — the nickname pattern would swallow the literal `/likes` path.
