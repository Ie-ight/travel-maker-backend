import os
from typing import Any

from celery import Celery
from decouple import config

os.environ.setdefault("DJANGO_SETTINGS_MODULE", config("DJANGO_SETTINGS_MODULE", default="config.settings.local"))

app = Celery("travel_maker")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_scheduler = "django_celery_beat.schedulers:DatabaseScheduler"


@app.task(bind=True, ignore_result=True)  # type: ignore[misc]
def debug_task(self: Any) -> None:
    """디버그용 테스트 태스크"""
    print(f"Request: {self.request!r}")
