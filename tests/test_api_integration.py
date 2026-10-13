from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from app.media import probe_video


def _seed_completed_project(api_runtime, *, render_status: str = "ready") -> tuple[str, str]:
    project_id = uuid.uuid4().hex
    clip_id = uuid.uuid4().hex
    api_runtime.store.create(
        {
            "id": project_id,
            "name": "API durum testi",
            "status": "completed",
            "stage": "complete",
            "progress": 100,
            "message": "Hazır",
            "error": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "settings": {},
            "source": {
                "stored_name": "source.mp4",
                "original_filename": "source.mp4",
                "duration": 30,
            },
            "analysis": None,
            "stages": [],
            "clips": [
                {
                    "id": clip_id,
                    "title": "Test klibi",
                    "start": 0,
                    "end": 10,
                    "duration": 10,
                    "render_status": render_status,
                    "render_progress": 100 if render_status == "ready" else 0,
                    "render": {
                        "video_file": "clip.mp4",
                        "poster_file": "poster.jpg",
                        "srt_file": "captions.srt",
                    },
                }
            ],
        }
    )
    clip_dir = api_runtime.store.project_dir(project_id) / "clips" / clip_id
    clip_dir.mkdir()
    (clip_dir / "clip.mp4").write_bytes(b"old-video")
    (clip_dir / "poster.jpg").write_bytes(b"old-poster")
    (clip_dir / "captions.srt").write_text("eski altyazı", encoding="utf-8")
    return project_id, clip_id


def test_health_reports_local_engine_and_security_headers(api_runtime) -> None:
    response = api_runtime.client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["local_only"] is True
    assert body["telemetry"] is False
    assert isinstance(body["engine"]["ffmpeg"], bool)
    assert isinstance(body["engine"]["ffprobe"], bool)
    assert body["system"]["disk_total"] > 0
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"


def test_api_docs_are_self_contained_and_protected(api_runtime) -> None:
    response = api_runtime.client.get("/api/docs")

    assert response.status_code == 200
    assert "jsdelivr" not in response.text.lower()
    assert "http://" not in response.text.lower()
    assert "https://" not in response.text.lower()
    assert "/api/openapi.json" in response.text
    assert "content-security-policy" in response.headers


def test_unknown_api_path_returns_json_404(api_runtime) -> None:
    response = api_runtime.client.get("/api/not-a-real-route")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_stale_render_artifacts_are_not_advertised_or_served(api_runtime) -> None:
    project_id, clip_id = _seed_completed_project(api_runtime, render_status="stale")

    project = api_runtime.client.get(f"/api/projects/{project_id}")
    assert project.status_code == 200
    clip = project.json()["clips"][0]
    assert clip["video_url"] is None
    assert clip["download_url"] is None
    assert clip["thumbnail_url"] is None
    assert clip["srt_url"] is None

    for suffix in ("media", "download", "poster", "captions.srt"):
        response = api_runtime.client.get(
            f"/api/projects/{project_id}/clips/{clip_id}/{suffix}"
        )
        assert response.status_code == 404


@pytest.mark.parametrize("render_status", ["queued", "rendering"])
def test_active_clip_blocks_patch_retry_and_delete(api_runtime, render_status: str) -> None:
    project_id, clip_id = _seed_completed_project(
        api_runtime,
        render_status=render_status,
    )

    patch_response = api_runtime.client.patch(
        f"/api/projects/{project_id}/clips/{clip_id}",
        json={"title": "Değiştirilmemeli"},
    )
    retry_response = api_runtime.client.post(f"/api/projects/{project_id}/retry")
    delete_response = api_runtime.client.delete(f"/api/projects/{project_id}")

    assert patch_response.status_code == 409
    assert retry_response.status_code == 409
    assert delete_response.status_code == 409
    assert api_runtime.store.get(project_id)["clips"][0]["title"] == "Test klibi"


def test_render_post_is_deduplicated_and_hides_previous_artifacts(
    api_runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as main_module

    project_id, clip_id = _seed_completed_project(api_runtime, render_status="ready")
    submitted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main_module.jobs,
        "submit_render",
        lambda queued_project_id, queued_clip_id: submitted.append(
            (queued_project_id, queued_clip_id)
        ),
    )

    first = api_runtime.client.post(
        f"/api/projects/{project_id}/clips/{clip_id}/render"
    )
    second = api_runtime.client.post(
        f"/api/projects/{project_id}/clips/{clip_id}/render"
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert submitted == [(project_id, clip_id)]
    assert first.json()["render_status"] == "queued"
    assert first.json()["video_url"] is None
    assert second.json()["video_url"] is None
    assert api_runtime.client.get(
        f"/api/projects/{project_id}/clips/{clip_id}/media"
    ).status_code == 404


def _make_synthetic_video(output: Path, duration: float = 6.0) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size=180x320:rate=8:duration={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=660:sample_rate=16000:duration={duration}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, timeout=30)


@pytest.mark.integration
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg and FFprobe are required for the local media integration test",
)
def test_upload_processing_polling_and_clip_output(api_runtime, tmp_path: Path) -> None:
    source = tmp_path / "synthetic.mp4"
    _make_synthetic_video(source)
    settings = {
        "min_duration": 5,
        "max_duration": 8,
        "clip_count": 1,
        "aspect_ratio": "9:16",
        "enable_captions": False,
    }

    with source.open("rb") as handle:
        response = api_runtime.client.post(
            "/api/projects",
            files={"file": (source.name, handle, "video/mp4")},
            data={"settings": json.dumps(settings)},
        )

    assert response.status_code == 202, response.text
    project_id = response.json()["id"]
    assert response.json()["status"] in {"queued", "processing", "completed"}

    deadline = time.monotonic() + 60
    project: dict[str, object] = {}
    observed_statuses: list[str] = []
    while time.monotonic() < deadline:
        poll = api_runtime.client.get(f"/api/projects/{project_id}")
        assert poll.status_code == 200
        project = poll.json()
        observed_statuses.append(str(project["status"]))
        if project["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)

    assert project.get("status") == "completed", (
        f"statuses={observed_statuses}; error={project.get('error')}; "
        f"message={project.get('message')}"
    )
    assert project["progress"] == 100
    assert len(project["clips"]) == 1

    clip = project["clips"][0]
    assert clip["render_status"] == "ready"
    assert 5 <= float(clip["duration"]) <= 8
    assert clip["video_url"]
    assert clip["download_url"]
    assert clip["thumbnail_url"]

    media_response = api_runtime.client.get(clip["video_url"])
    assert media_response.status_code == 200
    assert media_response.headers["content-type"].startswith("video/mp4")
    assert len(media_response.content) > 1_000

    output = (
        api_runtime.store.project_dir(project_id)
        / "clips"
        / clip["id"]
        / "clip.mp4"
    )
    assert output.is_file()
    metadata = probe_video(output)
    assert metadata["width"] == 1080
    assert metadata["height"] == 1920
    assert metadata["video_codec"] == "h264"
    assert metadata["duration"] == pytest.approx(float(clip["duration"]), abs=0.25)
