from django.urls import path

from apps.user.views.auth_views import (
    KakaoCallbackView,
    KakaoLoginView,
    LogoutView,
    RecoveryView,
    TokenRefreshView,
    WithdrawView,
)

urlpatterns = [
    # 카카오 로그인
    path("kakao/login", KakaoLoginView.as_view(), name="kakao-login"),
    path("kakao/callback", KakaoCallbackView.as_view(), name="kakao-callback"),
    # 세션 관리
    path("logout", LogoutView.as_view(), name="logout"),
    path("token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
    # 회원 탈퇴 / 복구
    path("withdraw", WithdrawView.as_view(), name="withdraw"),
    path("recovery", RecoveryView.as_view(), name="recovery"),
]
