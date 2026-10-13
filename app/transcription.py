from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from typing import Any, Callable

from .config import ALLOW_MODEL_DOWNLOAD, MODELS_DIR, WHISPER_MODEL


_MODEL: Any = None
_MODEL_KEY: str | None = None
_MODEL_LOCK = threading.Lock()


def faster_whisper_installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def configured_model() -> str | None:
    if WHISPER_MODEL:
        configured = Path(WHISPER_MODEL).expanduser()
        if configured.exists():
            return str(configured.resolve())
        if ALLOW_MODEL_DOWNLOAD:
            return WHISPER_MODEL
        candidate = MODELS_DIR / WHISPER_MODEL
        if candidate.exists():
            return str(candidate.resolve())
        return None
    preferred = [
        MODELS_DIR / "faster-whisper-small",
        MODELS_DIR / "faster-whisper-base",
        MODELS_DIR / "whisper",
    ]
    for candidate in preferred:
        if candidate.is_dir() and (candidate / "model.bin").is_file():
            return str(candidate.resolve())
    for candidate in MODELS_DIR.iterdir() if MODELS_DIR.exists() else []:
        if candidate.is_dir() and (candidate / "model.bin").is_file():
            return str(candidate.resolve())
    return None


def transcription_capability() -> dict[str, Any]:
    model = configured_model()
    package_installed = faster_whisper_installed()
    return {
        "available": package_installed and model is not None,
        "engine": "faster-whisper" if package_installed else None,
        "package_installed": package_installed,
        "model_configured": model is not None,
        "model": Path(model).name if model and Path(model).exists() else model,
        "download_allowed": ALLOW_MODEL_DOWNLOAD,
    }


def _load_model(model_reference: str) -> Any:
    global _MODEL, _MODEL_KEY
    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_KEY == model_reference:
            return _MODEL
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel(
            model_reference,
            device="cpu",
            compute_type="int8",
            cpu_threads=2,
            num_workers=1,
        )
        _MODEL_KEY = model_reference
        return _MODEL


def transcribe_video(
    source: Path,
    language: str = "auto",
    progress: Callable[[float], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model_reference = configured_model()
    if not faster_whisper_installed():
        return [], {"engine": "unavailable", "reason": "faster-whisper kurulu değil"}
    if not model_reference:
        return [], {
            "engine": "unavailable",
            "reason": "Yerel Whisper modeli yapılandırılmadı",
        }
    try:
        model = _load_model(model_reference)
        segments_iter, info = model.transcribe(
            str(source),
            language=None if language in {"", "auto"} else language,
            beam_size=5,
            best_of=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 450},
            word_timestamps=True,
            condition_on_previous_text=True,
        )
        duration = float(getattr(info, "duration", 0) or 0)
        segments: list[dict[str, Any]] = []
        for segment in segments_iter:
            words = []
            for word in segment.words or []:
                if word.start is None or word.end is None:
                    continue
                words.append(
                    {
                        "start": round(float(word.start), 3),
                        "end": round(float(word.end), 3),
                        "text": str(word.word).strip(),
                        "probability": round(float(word.probability or 0), 4),
                    }
                )
            item = {
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": str(segment.text).strip(),
                "words": words,
                "confidence": round(
                    max(0.0, min(1.0, 1.0 - float(getattr(segment, "no_speech_prob", 0) or 0))),
                    4,
                ),
            }
            segments.append(item)
            if progress and duration > 0:
                progress(min(0.98, item["end"] / duration))
        if progress:
            progress(1.0)
        return segments, {
            "engine": "faster-whisper",
            "model": Path(model_reference).name,
            "language": getattr(info, "language", language),
            "language_probability": round(float(getattr(info, "language_probability", 0) or 0), 4),
        }
    except Exception as exc:  # The heuristic pipeline must remain available offline.
        return [], {"engine": "failed", "reason": str(exc)[:500]}
