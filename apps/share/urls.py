from django.urls import path

from apps.share.views.share_views import ShareView

urlpatterns = [
    path("share", ShareView.as_view()),
]
