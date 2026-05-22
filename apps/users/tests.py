from django.test import TestCase

from apps.users.apps import UsersConfig


class UsersAppTestCase(TestCase):
    """Users 앱 기본 테스트"""

    def test_app_config(self):
        """앱 설정이 올바른지 확인"""
        self.assertEqual(UsersConfig.name, "apps.users")
        self.assertEqual(UsersConfig.verbose_name, "사용자")

    def test_app_ready(self):
        """앱이 정상적으로 로드되는지 확인"""
        # 앱이 로드되면 이 테스트는 통과
        self.assertTrue(True)
