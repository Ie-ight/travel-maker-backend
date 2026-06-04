"""Celery 태스크 테스트(단계 7 스케줄). 실제 sync/Gemini 호출 없이 위임만 검증한다."""

from typing import Any

from apps.place.services.place_sync import SyncSummary
from apps.place.tasks import ai_tag_missing_task, sync_incremental_task


def test_sync_incremental_task_위임(monkeypatch: Any) -> None:
    calls: dict[str, bool] = {}

    def fake_sync() -> SyncSummary:
        calls["called"] = True
        return SyncSummary(created=2, updated=1)

    monkeypatch.setattr("apps.place.tasks.sync_incremental", fake_sync)
    sync_incremental_task()
    assert calls.get("called") is True


def test_ai_tag_missing_task_위임(monkeypatch: Any) -> None:
    # call_command를 가로채 Gemini·일 한도(20)·분당(4)·only-missing로 위임하는지만 확인
    captured: dict[str, Any] = {}

    def fake_call_command(name: str, **opts: Any) -> None:
        captured["name"] = name
        captured["opts"] = opts

    monkeypatch.setattr("apps.place.tasks.call_command", fake_call_command)
    ai_tag_missing_task()
    assert captured["name"] == "ai_tag"
    assert captured["opts"] == {"provider": "gemini", "limit": 20, "rpm": 4, "only_missing": True}
