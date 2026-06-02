from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.user.models import SocialUser, User
from apps.user.services.auth_service import KakaoAuthService, KakaoUserInfo

# ── 헬퍼 ────────────────────────────────────────────────────────────────────


def make_user(email: str = "test@example.com", nickname: str = "traveler_10000") -> User:
    """테스트용 유저 생성"""
    user = User.objects.create_user(
        email=email,
        nickname=nickname,
        gender="M",
        birthday="1995-01-01",
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


def make_kakao_user_info(**kwargs: str | None) -> KakaoUserInfo:
    """테스트용 KakaoUserInfo 생성"""
    defaults: dict[str, str | None] = {
        "provider_id": "kakao_12345",
        "email": "kakao@example.com",
        "nickname": "카카오유저",
        "profile_img_url": "https://example.com/img.jpg",
        "gender": "M",
        "birthday": "1995-06-15",
    }
    defaults.update(kwargs)
    return KakaoUserInfo(**defaults)


# ── KakaoAuthService 단위 테스트 ─────────────────────────────────────────────


class KakaoAuthServiceTest(TestCase):
    # ── get_or_create_user ──────────────────────────────────────────────────

    @patch.object(KakaoAuthService, "get_user_info")
    @patch.object(KakaoAuthService, "get_access_token")
    def test_신규_유저_생성(self, mock_get_token: MagicMock, mock_get_info: MagicMock) -> None:
        """카카오 로그인 최초 시도 시 유저와 SocialUser가 생성된다."""
        mock_get_token.return_value = "fake_access_token"
        mock_get_info.return_value = make_kakao_user_info()

        user, is_new_user = KakaoAuthService.get_or_create_user("fake_code")

        self.assertTrue(is_new_user)
        self.assertEqual(user.email, "kakao@example.com")
        self.assertTrue(SocialUser.objects.filter(provider_id="kakao_12345").exists())

    @patch.object(KakaoAuthService, "get_user_info")
    @patch.object(KakaoAuthService, "get_access_token")
    def test_기존_유저_조회(self, mock_get_token: MagicMock, mock_get_info: MagicMock) -> None:
        """이미 가입된 카카오 유저는 새로 생성하지 않고 기존 유저를 반환한다."""
        mock_get_token.return_value = "fake_access_token"
        mock_get_info.return_value = make_kakao_user_info()

        user = make_user(email="kakao@example.com")
        SocialUser.objects.create(
            user=user,
            provider=SocialUser.Provider.KAKAO,
            provider_id="kakao_12345",
        )

        returned_user, is_new_user = KakaoAuthService.get_or_create_user("fake_code")

        self.assertFalse(is_new_user)
        self.assertEqual(returned_user.pk, user.pk)
        self.assertEqual(User.objects.count(), 1)

    @patch.object(KakaoAuthService, "get_user_info")
    @patch.object(KakaoAuthService, "get_access_token")
    def test_이메일_없는_카카오_계정_거부(self, mock_get_token: MagicMock, mock_get_info: MagicMock) -> None:
        """이메일 미동의 카카오 계정은 EmailNotProvidedError를 발생시킨다."""
        from apps.user.utils.auth_exceptions import EmailNotProvidedError

        mock_get_token.return_value = "fake_access_token"
        mock_get_info.return_value = make_kakao_user_info(email=None)

        with self.assertRaises(EmailNotProvidedError):
            KakaoAuthService.get_or_create_user("fake_code")

    # ── generate_token_pair ─────────────────────────────────────────────────

    def test_토큰_쌍_발급(self) -> None:
        """generate_token_pair는 access/refresh 토큰 문자열을 반환한다."""
        user = make_user()
        access, refresh = KakaoAuthService.generate_token_pair(user)

        self.assertIsInstance(access, str)
        self.assertIsInstance(refresh, str)
        self.assertTrue(len(access) > 0)
        self.assertTrue(len(refresh) > 0)

    # ── blacklist / is_blacklisted ──────────────────────────────────────────

    def test_블랙리스트_등록_및_확인(self) -> None:
        """로그아웃한 refresh token은 블랙리스트에서 True를 반환한다."""
        user = make_user()
        _, refresh_str = KakaoAuthService.generate_token_pair(user)

        KakaoAuthService.blacklist_token(refresh_str)

        self.assertTrue(KakaoAuthService.is_blacklisted(refresh_str))

    def test_블랙리스트_미등록_토큰(self) -> None:
        """블랙리스트에 없는 토큰은 False를 반환한다."""
        user = make_user()
        _, refresh_str = KakaoAuthService.generate_token_pair(user)

        self.assertFalse(KakaoAuthService.is_blacklisted(refresh_str))

    def test_만료된_토큰_블랙리스트_등록_무시(self) -> None:
        """만료되거나 유효하지 않은 토큰 등록 시 예외 없이 무시된다."""
        try:
            KakaoAuthService.blacklist_token("invalid.token.string")
        except Exception as e:
            self.fail(f"예외가 발생하면 안 됩니다: {e}")


# ── API View 통합 테스트 ──────────────────────────────────────────────────────


class KakaoLoginViewTest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("kakao-login")

    @patch.object(KakaoAuthService, "get_or_create_user")
    def test_기존_유저_로그인_200(self, mock_get_or_create: MagicMock) -> None:
        """기존 유저 로그인 시 200과 access_token을 반환한다."""
        user = make_user()
        mock_get_or_create.return_value = (user, False)

        res = self.client.post(self.url, {"code": "fake_code"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", res.data)
        self.assertFalse(res.data["is_new_user"])
        self.assertIn("refresh_token", res.cookies)

    @patch.object(KakaoAuthService, "get_or_create_user")
    def test_신규_유저_가입_201(self, mock_get_or_create: MagicMock) -> None:
        """신규 유저 가입 시 201과 access_token을 반환한다."""
        user = make_user()
        mock_get_or_create.return_value = (user, True)

        res = self.client.post(self.url, {"code": "fake_code"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("access_token", res.data)
        self.assertTrue(res.data["is_new_user"])

    def test_code_누락_400(self) -> None:
        """code 없이 요청 시 400을 반환한다."""
        res = self.client.post(self.url, {}, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error_detail", res.data)

    @patch.object(KakaoAuthService, "get_or_create_user")
    def test_카카오_서버_오류_503(self, mock_get_or_create: MagicMock) -> None:
        """카카오 서버 오류 시 503을 반환한다."""
        from apps.user.utils.auth_exceptions import KakaoServerError

        mock_get_or_create.side_effect = KakaoServerError()

        res = self.client.post(self.url, {"code": "fake_code"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("error_detail", res.data)


class LogoutViewTest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("logout")
        self.user = make_user()

    def _auth_header(self) -> str:
        access, _ = KakaoAuthService.generate_token_pair(self.user)
        return f"Bearer {access}"

    def test_로그아웃_성공_204(self) -> None:
        """인증된 유저가 로그아웃 시 204를 반환하고 쿠키가 삭제된다."""
        _, refresh_str = KakaoAuthService.generate_token_pair(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=self._auth_header())
        self.client.cookies["refresh_token"] = refresh_str

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_인증_없이_로그아웃_401(self) -> None:
        """인증 없이 로그아웃 요청 시 401을 반환한다."""
        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenRefreshViewTest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("token-refresh")
        self.user = make_user()

    def test_토큰_재발급_성공_200(self) -> None:
        """유효한 refresh token 쿠키로 새 access token을 발급받는다."""
        _, refresh_str = KakaoAuthService.generate_token_pair(self.user)
        self.client.cookies["refresh_token"] = refresh_str

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", res.data)

    def test_쿠키_없으면_403(self) -> None:
        """refresh token 쿠키가 없으면 403을 반환한다."""
        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_블랙리스트_토큰_403(self) -> None:
        """블랙리스트에 등록된 refresh token은 403을 반환한다."""
        _, refresh_str = KakaoAuthService.generate_token_pair(self.user)
        KakaoAuthService.blacklist_token(refresh_str)
        self.client.cookies["refresh_token"] = refresh_str

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_유효하지_않은_토큰_403(self) -> None:
        """유효하지 않은 토큰 문자열은 403을 반환한다."""
        self.client.cookies["refresh_token"] = "invalid.token.string"

        res = self.client.post(self.url)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
