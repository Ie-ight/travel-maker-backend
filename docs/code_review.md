# Travel Maker 백엔드 코드 리뷰

> 검토 일자: 2026-06-11
> 검토 범위: 전체 앱 (user, core, place, review, bookmark, travel_quiz, route)
> 검증 도구: `ruff check` (통과), `mypy` (195개 파일 무오류), `pytest` (88건 통과)

---

## 전체 평가

견고한 레이어드 아키텍처와 우수한 테스트 커버리지를 갖춘 프로덕션 지향 코드베이스입니다.
ruff/mypy 무오류, 일관된 레이어 분리, N+1 방어 의식이 돋보입니다.
다만 **🔴 심각 2건**은 배포 전 반드시 수정이 필요합니다.

### 심각도별 집계

| 심각도 | 건수 |
|---|---|
| 🔴 심각 (즉시 수정) | 2건 |
| 🟡 주의 (후속 수정) | 4건 |
| 🟢 개선 (선택) | 5건 |

---

## 1. 전체 아키텍처

**현재 상태**

`views → services → serializers → schemas → utils` 레이어 분리가 전 앱에 걸쳐 일관되게 지켜집니다.

- 뷰는 HTTP 파싱 + 서비스 호출만 담당
- 비즈니스 로직은 전부 서비스에 존재
- `apps/core`를 다른 앱이 단방향으로 의존 (역방향 없음)
- 순환 import는 `authentication.py`, `auth_service.py`에서 지역 import로 적절히 회피

**문제 없음.** 🟢 개선 수준의 이슈만 존재.

---

## 2. 앱별 구현 현황

| 앱 | 완성도 | 구현 기능 |
|---|---|---|
| `user` | 높음 | 카카오 OAuth2, 프로필, 팔로우, 어드민, 탈퇴/복구 |
| `core` | 높음 | TimeStampModel, 예외 핸들러, S3, 권한, 캐시 |
| `place` | 높음 | 목록/검색/필터/상세, AI 태깅, 벡터 추천, Tour API 동기화 |
| `review` | 높음 | CRUD, 소유자 검증, Celery 이미지 업로드, 평점 비정규화 |
| `bookmark` | 높음 | 추가/삭제/목록, unique 제약 |
| `travel_quiz` | 높음 | 6축 벡터 산출, 추천 연계 |
| `route` | 보통 | 모델/서비스/뷰 기본 구조 존재, 테스트 미작성 |

코드베이스 전체에서 `TODO` / `FIXME` / `print` 마커 **0건**으로 정리 상태 양호.

---

## 3. 보안

### 🔴 [심각] 프로덕션에서 SSL 리다이렉트 비활성화

**파일:** `config/settings/prod.py:20`

```python
SECURE_SSL_REDIRECT = False  # 주석은 "HTTP → HTTPS 자동 리다이렉트"라고 설명
```

주석은 HTTPS 강제를 설명하는데 값은 `False`로 모순입니다.
`SECURE_HSTS_SECONDS`(1년)는 켜져 있는데 리다이렉트가 꺼져 있어 첫 평문 접속이 그대로 노출됩니다.

**해결 방안:**
프록시(ALB/Nginx)에서 HTTPS를 종단하는 환경이라면 `SECURE_PROXY_SSL_HEADER`가 설정되어 있으므로 `True`로 변경해도 무한 리다이렉트가 발생하지 않습니다.

```python
SECURE_SSL_REDIRECT = True  # SECURE_PROXY_SSL_HEADER가 무한 루프 방지
```

의도적으로 끈 경우라면 주석을 "프록시에서 처리하므로 Django 레벨 비활성"으로 명확히 수정하세요.

---

### 🔴 [심각] SocialUser에 unique 제약 부재 → 동시 가입 시 중복 계정 생성 가능

**파일:** `apps/user/models.py:95-109`, `apps/user/services/auth_service.py:140-161`

`get_or_create_user`는 동시 가입 경쟁 조건을 `except IntegrityError`로 처리하도록 설계되어 있습니다(주석: "동시 요청으로 이미 생성된 경우").
그러나 `SocialUser` 모델에 `(provider, provider_id)` unique 제약이 **없어서** DB가 IntegrityError를 발생시키지 않습니다.
결과적으로 동일 카카오 계정으로 동시에 첫 로그인하면 **중복 User/SocialUser가 생성**됩니다.

**해결 방안:**

```python
# apps/user/models.py
class SocialUser(TimeStampModel):
    class Meta:
        db_table = "social_users"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_id"],
                name="unique_provider_account"
            )
        ]
```

마이그레이션을 추가하세요. (기존에 중복 데이터가 있다면 정리 후 적용.)

---

### 🟡 [주의] AdminLoginView에 어드민 권한 가드 없음

**파일:** `apps/user/views/auth_views.py:58-85`

docstring은 "is_staff 전용"이라고 명시하지만, 실제 코드는 `is_active` 여부만 확인합니다.
현재는 카카오 유저가 `set_unusable_password()` 처리되어 실질 위험이 낮지만,
향후 비밀번호 기반 일반 유저가 생기면 누구나 이 엔드포인트로 토큰을 발급받을 수 있습니다.

**해결 방안:**

```python
user = authenticate(request, username=email, password=password)
if user is None or not user.is_active:
    return Response({"error_detail": "..."}, status=401)
if not (user.is_staff or user.role == User.Role.ADMIN):
    return Response({"error_detail": "..."}, status=401)
```

---

### 🟡 [주의] 콜백에서 Access Token이 URL 쿼리 파라미터로 노출

**파일:** `apps/user/views/auth_views.py:225`

```python
redirect_url = f"{FRONTEND_URL}/auth/callback?access_token={access_token}&is_new_user=..."
```

URL은 브라우저 히스토리, 서버 액세스 로그, Referer 헤더에 남습니다.

**해결 방안:** 프래그먼트(`#`)로 변경하면 서버 로그와 Referer에 남지 않습니다.

```python
redirect_url = f"{FRONTEND_URL}/auth/callback#access_token={access_token}&is_new_user=..."
```

또는 일회용 교환 코드 방식으로 변경을 검토하세요.

---

### 🟢 [개선] 인가코드 일부 로깅

**파일:** `apps/user/views/auth_views.py:110`

```python
logger.info(f"카카오 로그인 시도: code={code[:10]}...")
```

인가코드는 1회용이라 위험은 낮으나, 운영 로그에 자격 증명 단편을 남기는 패턴은 지양을 권장합니다.

---

**잘 된 점:**
- 블랙리스트 기반 Access Token 즉시 무효화 (`BlacklistAwareJWTAuthentication`)
- Refresh Token의 HttpOnly + SameSite=None/Secure 처리
- 캐시 장애 시 fail-open 처리
- 리뷰/북마크 소유자 검증 일관 적용

---

## 4. 성능

### 🟡 [주의] UserBookmarkSerializer N+1 쿼리

**파일:** `apps/user/serializers/profile_serializer.py:165-167`

```python
def get_image_url(self, obj):
    image = obj.place.images.filter(is_main=True).first()  # prefetch 캐시 무시 → 행마다 쿼리
```

`profile_service.py`에서 `prefetch_related("place__images")`로 미리 적재했는데,
`.filter()`를 호출하면 prefetch 캐시를 우회해 북마크 행마다 추가 쿼리가 발생합니다.
같은 프로젝트의 `PlaceListSerializer`는 올바르게 파이썬에서 필터링하므로 일관성도 깨집니다.

**해결 방안:** `PlaceListSerializer` 패턴과 동일하게 수정

```python
def get_image_url(self, obj):
    for image in obj.place.images.all():  # prefetch 캐시 활용
        if image.is_main:
            return image.image_url
    return None
```

---

### 🟡 [주의] ProfileSerializer 카운트 다중 쿼리

**파일:** `apps/user/serializers/profile_serializer.py:20-26`

`follower_count`, `following_count`, `bookmark_count`, `review_count`가 각각 `.count()`를 호출해
단일 프로필 응답에 4회의 COUNT 쿼리가 발생합니다.

**해결 방안:** 뷰에서 `annotate`로 한 번에 집계

```python
user = User.objects.annotate(
    follower_count=Count("followings", distinct=True),
    following_count=Count("followers", distinct=True),
    ...
).get(pk=pk)
```

---

**잘 된 점:**
- `distinct=True`로 M2M JOIN 행 부풀림 방지
- 비정규화 `rating_count` 컬럼 활용 (COUNT JOIN 제거)
- HNSW 인기순 폴백의 Redis 캐싱 (ID만 저장)
- 벡터 검색에서 `SET LOCAL hnsw.iterative_scan`을 명시적 트랜잭션 안에 배치

---

## 5. 코드 품질 / 에러 핸들링

### 🟢 [개선] Bookmark 서비스 이중 쿼리

**파일:** `apps/bookmark/views.py:33-38`, `services.py:17-19`

뷰에서 `Place` 조회와 중복 체크를 수행한 뒤, 서비스가 다시 `get_object_or_404(Place)`를 호출해 Place를 2회 조회합니다.
DB의 `unique_user_place_bookmark` 제약이 최종 방어선이라 데이터 정합성은 안전하지만,
로직을 서비스로 일원화하고 `IntegrityError`를 `Conflict`로 변환하면 깔끔합니다.

---

### 🟢 [개선] BookmarkListView 페이지네이션 부재

**파일:** `apps/bookmark/views.py:16-24`

`BookmarkListView`는 전체 북마크를 페이지네이션 없이 반환합니다.
프로필의 `UserBookmarkView`는 페이지네이션이 적용되어 있어 일관성이 깨집니다.

---

### 🟢 [개선] TravelQuiz submit의 TravelType 미처리 예외

**파일:** `apps/travel_quiz/services/travel_quiz_services.py:146`

```python
TravelType.objects.get(type_key=type_key)  # DoesNotExist → 500
```

시드 누락 시 500 에러가 발생합니다. 도메인 예외로 감싸는 것을 권장합니다.

---

**잘 된 점:**
- `error_detail` 응답 형식의 전역 일관성 (`custom_exception_handler`)
- 리뷰 수정의 화이트리스트 필드 검증 (`_REVIEW_UPDATABLE_FIELDS`)
- `update_fields`로 부분 업데이트
- `select_for_update` + 트랜잭션으로 평점 갱신 경쟁 방지

---

## 6. 테스트 커버리지

**현재 상태:** 17개 테스트 파일, **345개 테스트 함수**, 88건 통과

| 영역 | 커버리지 |
|---|---|
| `follow_service` | 100% |
| `profile_view` | 100% |
| `auth_views` | 79% |
| management commands / AI 연동 | 미측정 |

**전체 라인 커버리지 53%**는 외부 API 연동 코드가 미측정에 포함된 수치이며, 핵심 서비스/뷰는 79~100%로 높습니다.

### 🟢 [개선] auth_service 카카오 외부 호출 테스트

`apps/user/services/auth_service.py:53-106`의 카카오 외부 API 호출 경로는
`responses` 또는 `requests-mock`으로 모킹 테스트를 추가하면 커버리지와 회귀 안전성이 높아집니다.

---

## 7. API 설계

**현재 상태:** RESTful 일관성 양호

- 리소스 기반 경로, 적절한 HTTP 메서드 사용
- 상태코드: 201(신규가입) / 200(로그인) / 204(삭제/탈퇴) / 403(세션만료)
- 에러 응답: `{"error_detail": "..."}` 전역 통일
- drf-spectacular 스키마가 `schemas/` 모듈로 분리

### 🟢 [개선] 세션 만료에 403 사용

**파일:** `apps/user/views/auth_views.py:165, 180`

토큰 갱신 실패에 `403 FORBIDDEN`을 사용하는데, 시맨틱상 `401 UNAUTHORIZED`가 더 적절합니다.
프론트엔드 계약이 403에 의존한다면 유지해도 무방합니다.

---

## 8. 미완성 / 확인 필요 항목

| 항목 | 파일 | 비고 |
|---|---|---|
| 프로덕션 파일 로깅 주석 처리 | `config/settings/prod.py:72-82` | Sentry 대체 여부 확인 필요 |
| `USE_S3` 기본값 `False` | `config/settings/prod.py:36` | 운영 배포 시 환경변수 `USE_S3=True` 설정 필수 |
| `apps/route` 테스트 미작성 | `apps/route/tests/` | 빈 파일만 존재 |

---

## 종합 권고

### 즉시 수정 (🔴 배포 전 필수)

1. **`apps/user/models.py`** — `SocialUser`에 `(provider, provider_id)` UniqueConstraint + 마이그레이션 추가
2. **`config/settings/prod.py`** — `SECURE_SSL_REDIRECT` 값/주석 모순 해소

### 후속 수정 (🟡 머지 후)

3. **`apps/user/views/auth_views.py`** — AdminLoginView 어드민 권한 가드 추가
4. **`apps/user/serializers/profile_serializer.py`** — UserBookmarkSerializer N+1 수정
5. **`apps/user/views/auth_views.py`** — 콜백 Access Token 쿼리 파라미터 노출 검토
6. **`apps/user/serializers/profile_serializer.py`** — ProfileSerializer 카운트 annotate 통합

### 선택 개선 (🟢)

7. `auth_service.py` 카카오 API 모킹 테스트 추가
8. `BookmarkListView` 페이지네이션 추가
9. `TravelQuiz` submit DoesNotExist 예외 처리
10. 콜백 인가코드 로깅 제거

---

## Ultra Review (2차 — feat/admin-login + fix/swagger-bearer-auth)

> 검토 일자: 2026-06-11
> 검토 범위: `feat/admin-login` + `fix/swagger-bearer-auth` diff
> 방법: 9개 독립 앵글 병렬 분석 + Sweep

### 최종 결과 (심각도순 8건)

| 순위 | 심각도 | 파일 | 라인 | 내용 |
|---|---|---|---|---|
| 1 | 🔴 | `auth_views.py` | 77 | `is_staff` 가드 누락 |
| 2 | 🔴 | `auth_views.py` | 183 | Refresh token 로테이션 미구현 |
| 3 | 🔴 | `base.py` | 345 | `KAKAO_REST_API_KEY` 잘못된 env var 매핑 |
| 4 | 🟡 | `auth_views.py` | 68 | `is_valid()` 실패 → 401 반환 (400이어야 함) |
| 5 | 🟡 | `base.py` | 227 | `SECURITY` 전역 설정 비권장 |
| 6 | 🟢 | `auth_views.py` | 77 | `is_active` dead code |
| 7 | 🟢 | `auth_views.py` | 76 | `authenticate()` 레이어 위반 |
| 8 | 🟢 | `auth_schemas.py` | 160 | 쿠키 사이드이펙트 미문서화 |

---

### 🔴 [1] AdminLoginView에 `is_staff` 가드 누락

**파일:** `apps/user/views/auth_views.py:77`

docstring·스키마는 "is_staff 전용"이라 명시하지만 실제 코드는 `is_active`만 확인합니다.

```python
# 현재
user = authenticate(request, username=email, password=password)
if user is None or not user.is_active:
    return Response(...)

# 수정
if user is None:
    return Response(...)
if not user.is_staff:
    return Response(...)
```

**실패 시나리오:** 향후 일반 유저에게 직접 비밀번호를 설정하는 경로가 생기면 누구나 이 엔드포인트로 JWT 발급 가능.

---

### 🔴 [2] TokenRefreshView가 `ROTATE_REFRESH_TOKENS=True` 설정을 이행하지 않음

**파일:** `apps/user/views/auth_views.py:183`

`SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] = True`로 설정되어 있지만, 커스텀 `TokenRefreshView`는 `RefreshToken(str)`을 파싱만 하고 SimpleJWT의 `TokenRefreshSerializer` 로테이션 로직을 거치지 않습니다.

**실패 시나리오:** refresh token이 만료 전까지 영구 재사용 가능. 탈취된 refresh token이 로테이션으로 무효화되지 않아 세션 탈취 지속 가능.

**해결 방안:** 토큰 재발급 시 새 refresh token을 발급하고 쿠키에 덮어씌우거나, `ROTATE_REFRESH_TOKENS = False`로 설정을 실제 동작에 맞춤.

```python
# TokenRefreshView.post() 수정안
token = RefreshToken(refresh_token_str)
new_refresh = token  # 로테이션 시 새 토큰 발급
access_token = str(token.access_token)

response = Response({"access_token": access_token}, status=200)
_set_refresh_cookie(response, str(new_refresh))  # 쿠키 갱신
return response
```

---

### 🔴 [3] `KAKAO_REST_API_KEY`가 `KAKAO_CLIENT_ID` env var로 잘못 초기화됨

**파일:** `config/settings/base.py:345`

```python
KAKAO_CLIENT_ID    = os.getenv("KAKAO_CLIENT_ID")       # ✅ 정상
KAKAO_JS_KEY       = os.getenv("KAKAO_JS_KEY", "")       # ✅ 정상
KAKAO_REST_API_KEY = os.getenv("KAKAO_CLIENT_ID", "")    # ❌ 오타
```

`KAKAO_REST_API_KEY`는 `apps/place/services/map_api_service.py`에서 **카카오 지도 API** 호출에 사용됩니다. `KAKAO_REST_API_KEY` 환경변수를 설정해도 완전히 무시되고 항상 `KAKAO_CLIENT_ID` 값이 사용됩니다.

**실패 시나리오:** 두 키가 다른 값이거나 분리 설정할 경우 지도 API 전체 불가.

**해결 방안:**
```python
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")  # KAKAO_CLIENT_ID → KAKAO_REST_API_KEY
```

---

### 🟡 [4] Serializer `is_valid()` 실패 시 400이 아닌 401 반환

**파일:** `apps/user/views/auth_views.py:68`

이메일 형식 오류·필드 누락 등 입력 오류 시 401 Unauthorized 반환. 시맨틱상 클라이언트 입력 오류는 400 Bad Request입니다.

```python
# 수정
if not serializer.is_valid():
    return Response({"error_detail": "..."}, status=status.HTTP_400_BAD_REQUEST)
```

---

### 🟡 [5] `SECURITY` 전역 설정이 drf-spectacular 비권장

**파일:** `config/settings/base.py:227`

drf-spectacular는 `SECURITY` 전역 설정을 **STRONGLY DISCOURAGED**로 명시합니다. 이 설정이 있으면 `permission_classes=[]`인 엔드포인트(카카오 로그인, 토큰 재발급 등)에도 BearerAuth가 필요한 것처럼 Swagger에 표시됩니다.

**해결 방안:** `SECURITY` 제거 후, 인증이 필요한 뷰에만 `@extend_schema(security=[{"BearerAuth": []}])` 적용.

---

### 🟢 [6] `not user.is_active` 체크가 dead code

**파일:** `apps/user/views/auth_views.py:77`

Django `ModelBackend.authenticate()`가 `is_active=False` 유저에게 이미 `None`을 반환합니다. 뷰의 추가 검사는 절대 `True`가 되지 않는 데드 브랜치입니다.

---

### 🟢 [7] `authenticate()` 직접 호출이 views→services 레이어 규칙 위반

**파일:** `apps/user/views/auth_views.py:76`

`CLAUDE.md` 규칙: "비즈니스 로직은 service에만". `KakaoAuthService`에 `login_with_password()` 스태틱 메서드로 추출하면 [1], [6] 이슈도 함께 해결됩니다.

---

### 🟢 [8] `admin_login_schema`가 refresh_token 쿠키 사이드이펙트를 문서화하지 않음

**파일:** `apps/user/schemas/auth_schemas.py:160`

뷰는 `_set_refresh_cookie()`를 호출해 `Set-Cookie: refresh_token` 헤더를 내리지만 OpenAPI 스키마에 없습니다. Swagger 사용자가 admin login 후 쿠키가 발급되는지, `/token/refresh`에 사용 가능한지 알 수 없습니다.

---

### 1차 리뷰 대비 신규 발견 이슈

1차 리뷰에서 잡지 못한 항목:
- **`TokenRefreshView` 로테이션 미구현** — 설정과 실제 동작 불일치, 탈취 토큰 무효화 불가
- **`KAKAO_REST_API_KEY` 오타** — 지도 API 환경변수 잘못 매핑
