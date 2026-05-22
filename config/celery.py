"""
Celery configuration for travel-maker project.
"""
import os
from celery import Celery
from decouple import config

# Django settings module 설정
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    config("DJANGO_SETTINGS_MODULE", default="config.settings.local")
)

app = Celery("travel_maker")

# Django settings에서 CELERY_ 접두사가 붙은 설정을 로드
app.config_from_object("django.conf:settings", namespace="CELERY")

# 모든 Django 앱에서 tasks.py를 자동으로 찾아서 등록
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """디버그용 테스트 태스크"""
    print(f"Request: {self.request!r}")