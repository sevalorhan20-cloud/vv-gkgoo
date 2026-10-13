from __future__ import annotations

import importlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@dataclass(frozen=True)
class ApiRuntime:
    client: TestClient
    store: Any


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: exercises the real local FFmpeg processing pipeline",
    )


@pytest.fixture()
def api_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ApiRuntime]:
    """Run the FastAPI app against an isolated store and a single local worker."""
    from app import config as config_module

    data_dir = tmp_path / "data"
    projects_dir = data_dir / "projects"
    models_dir = tmp_path / "models"
    frontend_dist = tmp_path / "frontend-dist"

    monkeypatch.setattr(config_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(config_module, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(config_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(config_module, "FRONTEND_DIST", frontend_dist)

    # app.main may already be cached by another test. Patch every module-level
    # binding used by the app instead of relying on import order.
    main_module = importlib.import_module("app.main")
    pipeline_module = importlib.import_module("app.pipeline")
    transcription_module = importlib.import_module("app.transcription")
    store_module = importlib.import_module("app.store")

    monkeypatch.setattr(transcription_module, "MODELS_DIR", models_dir)
    monkeypatch.setattr(transcription_module, "WHISPER_MODEL", "")
    monkeypatch.setattr(transcription_module, "ALLOW_MODEL_DOWNLOAD", False)

    projects_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    isolated_store = store_module.ProjectStore(projects_dir)
    isolated_jobs = pipeline_module.JobManager(isolated_store)

    monkeypatch.setattr(main_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(main_module, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(main_module, "FRONTEND_DIST", frontend_dist)
    monkeypatch.setattr(main_module, "store", isolated_store)
    monkeypatch.setattr(main_module, "jobs", isolated_jobs)

    # Keep this suite fast and offline while retaining the real media analysis,
    # scoring, persistence, job polling, and render path.
    def deterministic_transcription(
        _source: Path,
        language: str = "auto",
        progress: Any = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if progress:
            progress(1.0)
        return [], {"engine": "test-stub", "language": language}

    monkeypatch.setattr(pipeline_module, "transcribe_video", deterministic_transcription)
    monkeypatch.setattr(
        pipeline_module,
        "detect_focus_x",
        lambda *_args, **_kwargs: {
            "focus_x": 0.5,
            "engine": "test-center",
            "detections": 0,
        },
    )

    try:
        with TestClient(main_module.app) as client:
            yield ApiRuntime(client=client, store=isolated_store)
    finally:
        isolated_jobs.executor.shutdown(wait=True, cancel_futures=True)
