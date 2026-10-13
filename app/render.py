from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

from .captions import create_ass_subtitles, create_srt_subtitles
from .media import MediaError, make_thumbnail, parse_ffmpeg_progress


RESOLUTIONS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


def _subtitle_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", r"\:").replace("'", r"\'")
    return value


def _render_clip_into(
    source: Path,
    output_dir: Path,
    clip: dict[str, Any],
    source_metadata: dict[str, Any],
    transcript: list[dict[str, Any]],
    progress: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    start = max(0.0, float(clip["start"]))
    end = min(float(source_metadata["duration"]), float(clip["end"]))
    duration = end - start
    if duration <= 0.05:
        raise MediaError("Klip zaman aralığı geçersiz")
    aspect = clip.get("aspect_ratio") or "9:16"
    width, height = RESOLUTIONS.get(aspect, RESOLUTIONS["9:16"])
    focus_x = min(1.0, max(0.0, float(clip.get("focus_x", 0.5))))
    video_path = output_dir / "clip.mp4"
    poster_path = output_dir / "poster.jpg"
    ass_path = output_dir / "captions.ass"
    srt_path = output_dir / "captions.srt"

    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}:x='max(0,min(iw-ow,iw*{focus_x:.6f}-ow/2))':y='max(0,(ih-oh)/2)'",
    ]
    has_captions = False
    if clip.get("enable_captions", True) and transcript:
        has_captions = create_ass_subtitles(
            ass_path,
            transcript,
            start,
            end,
            preset_name=clip.get("caption_preset", "impact"),
            resolution=(width, height),
            primary_color=clip.get("caption_color", "#FFFFFF"),
            highlight_color=clip.get("highlight_color", "#65E6B4"),
            font_size=clip.get("font_size"),
            position=clip.get("caption_position", "bottom"),
        )
        create_srt_subtitles(srt_path, transcript, start, end)
        if has_captions:
            filters.append(f"subtitles=filename='{_subtitle_filter_path(ass_path)}'")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        ",".join(filters),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
    ]
    if source_metadata.get("has_audio"):
        command.extend(
            [
                "-af",
                "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
            ]
        )
    command.extend(
        [
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(video_path),
        ]
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    return_code, stderr = parse_ffmpeg_progress(process, duration, progress)
    if return_code != 0:
        raise MediaError(stderr[-1800:] or "Klip render işlemi başarısız")
    make_thumbnail(video_path, poster_path, min(1.5, max(0.1, duration / 2)), width=480)
    return {
        "video_file": video_path.name,
        "poster_file": poster_path.name,
        "ass_file": ass_path.name if has_captions else None,
        "srt_file": srt_path.name if srt_path.exists() else None,
        "width": width,
        "height": height,
        "duration": round(duration, 3),
        "size": video_path.stat().st_size,
    }


def render_clip(
    source: Path,
    output_dir: Path,
    clip: dict[str, Any],
    source_metadata: dict[str, Any],
    transcript: list[dict[str, Any]],
    progress: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Render privately, then atomically publish the completed artifact set."""

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = output_dir.parent / f".{output_dir.name}.render-{uuid.uuid4().hex}"
    staging_dir.mkdir(exist_ok=False)
    try:
        result = _render_clip_into(
            source,
            staging_dir,
            clip,
            source_metadata,
            transcript,
            progress,
        )
        artifact_fields = {
            "video_file": "clip.mp4",
            "poster_file": "poster.jpg",
            "ass_file": "captions.ass",
            "srt_file": "captions.srt",
        }
        produced: set[str] = set()
        for field, expected_name in artifact_fields.items():
            filename = result.get(field)
            if not filename:
                continue
            if filename != expected_name:
                raise MediaError("Render beklenmeyen bir çıktı adı üretti")
            staged_path = staging_dir / filename
            if not staged_path.is_file():
                raise MediaError(f"Render çıktısı eksik: {filename}")
            produced.add(filename)

        if not {"clip.mp4", "poster.jpg"}.issubset(produced):
            raise MediaError("Render video veya kapak görseli üretmedi")

        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("clip.mp4", "poster.jpg", "captions.ass", "captions.srt"):
            if filename in produced:
                os.replace(staging_dir / filename, output_dir / filename)

        # A successful caption-free rerender must not inherit old subtitle files.
        for filename in {"captions.ass", "captions.srt"} - produced:
            (output_dir / filename).unlink(missing_ok=True)
        return result
    finally:
        # Only this job's uniquely named staging directory is ever cleaned here.
        shutil.rmtree(staging_dir, ignore_errors=True)
