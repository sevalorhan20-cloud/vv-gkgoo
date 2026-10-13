from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app import render as render_module
from app.media import MediaError


def test_caption_free_render_removes_old_sidecars_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "clip-id"
    output_dir.mkdir()
    (output_dir / "clip.mp4").write_bytes(b"old-video")
    (output_dir / "poster.jpg").write_bytes(b"old-poster")
    (output_dir / "captions.ass").write_text("old ass", encoding="utf-8")
    (output_dir / "captions.srt").write_text("STALE SECRET", encoding="utf-8")

    def fake_render(
        _source: Path,
        staging_dir: Path,
        _clip: dict[str, Any],
        _metadata: dict[str, Any],
        _transcript: list[dict[str, Any]],
        _progress: Any,
    ) -> dict[str, Any]:
        assert staging_dir != output_dir
        (staging_dir / "clip.mp4").write_bytes(b"new-video")
        (staging_dir / "poster.jpg").write_bytes(b"new-poster")
        return {
            "video_file": "clip.mp4",
            "poster_file": "poster.jpg",
            "ass_file": None,
            "srt_file": None,
            "width": 1080,
            "height": 1920,
            "duration": 5,
            "size": 9,
        }

    monkeypatch.setattr(render_module, "_render_clip_into", fake_render)

    result = render_module.render_clip(
        tmp_path / "source.mp4",
        output_dir,
        {"start": 0, "end": 5, "enable_captions": False},
        {"duration": 5, "has_audio": False},
        [],
    )

    assert result["srt_file"] is None
    assert (output_dir / "clip.mp4").read_bytes() == b"new-video"
    assert (output_dir / "poster.jpg").read_bytes() == b"new-poster"
    assert not (output_dir / "captions.ass").exists()
    assert not (output_dir / "captions.srt").exists()
    assert list(tmp_path.glob(".clip-id.render-*")) == []


def test_failed_render_keeps_previous_artifacts_and_cleans_only_its_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "clip-id"
    output_dir.mkdir()
    (output_dir / "clip.mp4").write_bytes(b"last-good-video")
    unrelated = tmp_path / ".clip-id.render-unrelated"
    unrelated.mkdir()
    (unrelated / "keep.txt").write_text("keep", encoding="utf-8")

    def fail_render(
        _source: Path,
        staging_dir: Path,
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        (staging_dir / "clip.mp4").write_bytes(b"partial-video")
        raise MediaError("planned render failure")

    monkeypatch.setattr(render_module, "_render_clip_into", fail_render)

    with pytest.raises(MediaError, match="planned render failure"):
        render_module.render_clip(
            tmp_path / "source.mp4",
            output_dir,
            {"start": 0, "end": 5},
            {"duration": 5, "has_audio": False},
            [],
        )

    assert (output_dir / "clip.mp4").read_bytes() == b"last-good-video"
    assert (unrelated / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in tmp_path.glob(".clip-id.render-*")) == [
        unrelated.name
    ]
