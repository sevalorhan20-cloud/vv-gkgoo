from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("KLIPFORGE_DATA_DIR", ROOT_DIR / "data")).expanduser().resolve()
PROJECTS_DIR = DATA_DIR / "projects"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
MODELS_DIR = Path(os.getenv("KLIPFORGE_MODELS_DIR", ROOT_DIR / "models")).expanduser().resolve()

MAX_UPLOAD_BYTES = int(os.getenv("KLIPFORGE_MAX_UPLOAD_BYTES", str(8 * 1024**3)))
MAX_VIDEO_SECONDS = int(os.getenv("KLIPFORGE_MAX_VIDEO_SECONDS", str(6 * 60 * 60)))
WORKER_COUNT = max(1, int(os.getenv("KLIPFORGE_WORKERS", "1")))

WHISPER_MODEL = os.getenv("KLIPFORGE_WHISPER_MODEL", "").strip()
WHISPER_LANGUAGE = os.getenv("KLIPFORGE_WHISPER_LANGUAGE", "").strip()
ALLOW_MODEL_DOWNLOAD = os.getenv("KLIPFORGE_ALLOW_MODEL_DOWNLOAD", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OLLAMA_MODEL = os.getenv("KLIPFORGE_OLLAMA_MODEL", "").strip()
OLLAMA_URL = os.getenv("KLIPFORGE_OLLAMA_URL", "http://127.0.0.1:11434").strip().rstrip("/")

ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".m4v",
    ".avi",
    ".mpg",
    ".mpeg",
}


def ensure_directories() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
