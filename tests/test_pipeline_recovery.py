from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app import pipeline
from app.pipeline import JobManager, now_iso
from app.store import ProjectStore


def _project_record(
    project_id: str,
    *,
    status: str,
    clip_status: str | None = None,
) -> dict[str, Any]:
    clips = []
    if clip_status:
        clips.append(
            {
                "id": uuid.uuid4().hex,
                "start": 0.0,
                "end": 6.0,
                "duration": 6.0,
                "render_status": clip_status,
                "render_progress": 45,
                "render_error": None,
                "render": None,
            }
        )
    return {
        "id": project_id,
        "name": "Test",
        "status": status,
        "stage": "render",
        "progress": 70,
        "message": None,
        "error": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "settings": {},
        "source": {"stored_name": "source.mp4", "duration": 6.0, "has_audio": False},
        "analysis": None,
        "stages": [
            {"key": "render", "label": "Render", "status": "running", "progress": 45, "detail": None}
        ],
        "clips": clips,
    }


def test_recovery_normalizes_orphan_upload_and_clip_render(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    upload_id = str(uuid.uuid4())
    render_id = str(uuid.uuid4())
    store.create(_project_record(upload_id, status="uploading"))
    store.create(_project_record(render_id, status="completed", clip_status="rendering"))
    manager = JobManager(store)

    try:
        manager.recover_interrupted()
        upload = store.get(upload_id)
        rendered = store.get(render_id)

        assert upload["status"] == "failed"
        assert upload["error"]
        assert rendered["status"] == "completed"
        assert rendered["clips"][0]["render_status"] == "failed"
        assert rendered["clips"][0]["render_progress"] == 0
        assert rendered["stages"][0]["status"] == "error"
    finally:
        manager.shutdown()


def test_failed_manual_render_keeps_completed_project_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path / "projects")
    project_id = str(uuid.uuid4())
    record = _project_record(project_id, status="completed", clip_status="queued")
    record["stage"] = "complete"
    record["stages"][0].update({"status": "done", "progress": 100})
    store.create(record)
    manager = JobManager(store)

    def fail_render(*_args: Any, progress=None, **_kwargs: Any) -> dict[str, Any]:
        if progress:
            progress(0.5)
        raise RuntimeError("bilinçli render hatası")

    monkeypatch.setattr(pipeline, "render_clip", fail_render)
    try:
        manager._render_one_clip_job(project_id, record["clips"][0]["id"])
        project = store.get(project_id)

        assert project["status"] == "completed"
        assert project["stage"] == "complete"
        assert project["clips"][0]["render_status"] == "failed"
        assert "bilinçli" in project["clips"][0]["render_error"]
    finally:
        manager.shutdown()
