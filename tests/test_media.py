from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app import media as media_module
from app.media import MediaError, probe_video


def test_probe_video_falls_back_from_non_finite_format_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "metadata.webm"
    source.write_bytes(b"local-video-bytes")
    payload = {
        "format": {"duration": "N/A", "size": "N/A", "bit_rate": "inf"},
        "streams": [
            {
                "codec_type": "video",
                "duration": "12.5",
                "width": "640",
                "height": "360",
                "avg_frame_rate": "nan",
                "r_frame_rate": "30/1",
                "codec_name": "vp9",
            }
        ],
    }
    monkeypatch.setattr(
        media_module,
        "run_command",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(payload).encode("utf-8"),
            stderr=b"",
        ),
    )

    metadata = probe_video(source)

    assert metadata["duration"] == 12.5
    assert metadata["size"] == source.stat().st_size
    assert metadata["bit_rate"] == 0
    assert metadata["fps"] == 0


def test_probe_video_rejects_when_all_duration_values_are_non_finite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "unknown.mp4"
    source.write_bytes(b"x")
    payload = {
        "format": {"duration": "NaN"},
        "streams": [{"codec_type": "video", "duration": "inf"}],
    }
    monkeypatch.setattr(
        media_module,
        "run_command",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(payload).encode("utf-8"),
            stderr=b"",
        ),
    )

    with pytest.raises(MediaError, match="süresi belirlenemedi"):
        probe_video(source)
