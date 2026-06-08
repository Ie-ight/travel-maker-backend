from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.place.urls import tag_urlpatterns

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),
    # auth 연결
    path("api/v1/auth/", include("apps.user.urls.auth_urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # App URLs
    # path("api/user/", include("apps.user.urls")),
    path("api/v1/", include("apps.review.urls")),
    path("api/v1/", include("apps.user.urls.user_urls")),
    path("api/v1/admin/", include("apps.user.urls.admin_urls")),
    # path("api/users/", include("apps.users.urls")),
    path("api/v1/bookmarks/", include("apps.bookmark.urls")),
    path("api/v1/", include("apps.place.urls")),
    path("api/v1/tags/", include(tag_urlpatterns)),
]
# Static & Media files (개발 환경에서만)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Django Debug Toolbar (개발 환경에서만)
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
