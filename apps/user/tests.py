from django.test import TestCase

from apps.user.apps import UserConfig


class UsersAppTestCase(TestCase):
    """Users 앱 기본 테스트"""

    def test_app_config(self) -> None:
        """앱 설정이 올바른지 확인"""
        self.assertEqual(UserConfig.name, "apps.user")
        self.assertEqual(UserConfig.verbose_name, "사용자")

    def test_app_ready(self) -> None:
        """앱이 정상적으로 로드되는지 확인"""
        # 앱이 로드되면 이 테스트는 통과
        self.assertTrue(True)
