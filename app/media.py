from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import numpy as np


class MediaError(RuntimeError):
    pass


def binary_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(
    args: list[str],
    *,
    timeout: float | None = None,
    capture_stdout: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaError(f"Medya komutu çalıştırılamadı: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-1800:].strip()
        raise MediaError(detail or f"Komut {result.returncode} koduyla sonlandı")
    return result


def _finite_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _fraction(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    if "/" in value:
        left, right = value.split("/", 1)
        numerator = _finite_number(left)
        denominator = _finite_number(right)
        if numerator is None or denominator is None or denominator == 0:
            return 0.0
        result = numerator / denominator
        return result if math.isfinite(result) else 0.0
    parsed = _finite_number(value)
    if parsed is None:
        return 0.0
    return parsed


def probe_video(path: Path) -> dict[str, Any]:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        timeout=60,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError("FFprobe çıktısı okunamadı") from exc
    video_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        raise MediaError("Dosyada okunabilir bir video akışı yok")
    audio_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )
    format_info = payload.get("format") or {}
    duration = next(
        (
            candidate
            for candidate in (
                _finite_number(format_info.get("duration")),
                _finite_number(video_stream.get("duration")),
            )
            if candidate is not None and candidate > 0
        ),
        0.0,
    )
    if duration <= 0:
        raise MediaError("Video süresi belirlenemedi")
    rotation = 0
    tags = video_stream.get("tags") or {}
    side_data = video_stream.get("side_data_list") or []
    try:
        rotation = int(tags.get("rotate") or next((x.get("rotation") for x in side_data if "rotation" in x), 0))
    except (TypeError, ValueError):
        rotation = 0
    width_value = _finite_number(video_stream.get("width"))
    height_value = _finite_number(video_stream.get("height"))
    width = int(width_value) if width_value is not None and width_value > 0 else 0
    height = int(height_value) if height_value is not None and height_value > 0 else 0
    if abs(rotation) in {90, 270}:
        width, height = height, width
    size_value = _finite_number(format_info.get("size"))
    bit_rate_value = _finite_number(format_info.get("bit_rate"))
    return {
        "duration": round(duration, 3),
        "width": width,
        "height": height,
        "fps": round(_fraction(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")), 3),
        "video_codec": video_stream.get("codec_name") or "unknown",
        "audio_codec": (audio_stream or {}).get("codec_name"),
        "has_audio": audio_stream is not None,
        "size": int(size_value) if size_value is not None and size_value > 0 else path.stat().st_size,
        "bit_rate": int(bit_rate_value) if bit_rate_value is not None and bit_rate_value > 0 else 0,
    }


def make_thumbnail(source: Path, output: Path, at: float, width: int = 640) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(0, at):.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "3",
            str(output),
        ],
        timeout=90,
    )


def extract_audio_energy(
    source: Path,
    work_dir: Path,
    *,
    sample_rate: int = 8000,
    window_seconds: float = 0.5,
) -> tuple[list[float], float]:
    pcm_path = work_dir / "audio-analysis.pcm"
    run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            str(pcm_path),
        ],
        timeout=None,
        capture_stdout=False,
    )
    try:
        samples = np.memmap(pcm_path, dtype=np.int16, mode="r")
        window = max(1, int(sample_rate * window_seconds))
        count = int(math.ceil(len(samples) / window))
        rms = np.empty(count, dtype=np.float32)
        for index in range(count):
            chunk = np.asarray(samples[index * window : (index + 1) * window], dtype=np.float32)
            rms[index] = float(np.sqrt(np.mean(chunk * chunk))) if chunk.size else 0.0
        if rms.size:
            floor = float(np.percentile(rms, 10))
            ceiling = float(np.percentile(rms, 95))
            scale = max(1.0, ceiling - floor)
            normalized = np.clip((rms - floor) / scale, 0, 1)
            values = normalized.round(5).tolist()
        else:
            values = []
    finally:
        try:
            del samples
        except UnboundLocalError:
            pass
        pcm_path.unlink(missing_ok=True)
    return values, window_seconds


def detect_scenes(source: Path, sensitivity: float = 0.30) -> list[float]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        str(source),
        "-an",
        "-vf",
        f"scale=320:-2,select='gt(scene,{sensitivity:.3f})',showinfo",
        "-vsync",
        "vfr",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            timeout=None,
        )
    except OSError:
        return []
    text = result.stderr.decode("utf-8", errors="replace")
    points = [float(match) for match in re.findall(r"pts_time:([0-9.]+)", text)]
    deduplicated: list[float] = []
    for point in sorted(points):
        if not deduplicated or point - deduplicated[-1] >= 0.4:
            deduplicated.append(round(point, 3))
    return deduplicated


def parse_ffmpeg_progress(
    process: subprocess.Popen[str],
    duration: float,
    callback: Callable[[float], None] | None = None,
) -> tuple[int, str]:
    stderr = ""
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.strip()
        if line.startswith("out_time_ms=") and callback and duration > 0:
            try:
                seconds = int(line.split("=", 1)[1]) / 1_000_000
                callback(min(1.0, max(0.0, seconds / duration)))
            except ValueError:
                pass
    if process.stderr is not None:
        stderr = process.stderr.read()
    return process.wait(), stderr
