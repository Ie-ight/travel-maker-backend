"""
Django 프로젝트가 시작될 때 Celery를 자동으로 로드합니다.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
