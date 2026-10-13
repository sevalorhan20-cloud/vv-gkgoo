from __future__ import annotations

import json
import mimetypes
import os
import platform
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from . import __version__
from .config import (
    ALLOWED_VIDEO_EXTENSIONS,
    DATA_DIR,
    FRONTEND_DIST,
    MAX_UPLOAD_BYTES,
    MAX_VIDEO_SECONDS,
    PROJECTS_DIR,
    ROOT_DIR,
    ensure_directories,
)
from .media import MediaError, binary_available, probe_video
from .pipeline import JobManager, new_stages, now_iso
from .reframe import opencv_available
from .schemas import ClipUpdate, ProjectSettings
from .semantic import semantic_capability
from .store import ProjectStore
from .transcription import transcription_capability


ensure_directories()
store = ProjectStore(PROJECTS_DIR)
jobs = JobManager(store)

_ACTIVE_PROJECT_STATUSES = {"processing", "queued", "uploading"}
_ACTIVE_RENDER_STATUSES = {"queued", "rendering"}
_RENDER_ARTIFACT_KEYS = {
    "clip.mp4": "video_file",
    "poster.jpg": "poster_file",
    "captions.srt": "srt_file",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    jobs.recover_interrupted()
    try:
        yield
    finally:
        jobs.shutdown()


app = FastAPI(
    title="KlipForge Local",
    description="Tamamen yerel video highlight ve kısa klip üretim motoru",
    version=__version__,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def local_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers[
        "Content-Security-Policy"
    ] = "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'"
    return response


def _find_clip(project: dict[str, Any], clip_id: str) -> dict[str, Any]:
    clip = next((item for item in project.get("clips", []) if item.get("id") == clip_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Klip bulunamadı")
    return clip


def _has_active_render(project: dict[str, Any]) -> bool:
    return any(
        clip.get("render_status") in _ACTIVE_RENDER_STATUSES
        for clip in project.get("clips", [])
    )


def _ensure_project_idle(project: dict[str, Any], detail: str) -> None:
    if project.get("status") in _ACTIVE_PROJECT_STATUSES or _has_active_render(project):
        raise HTTPException(status_code=409, detail=detail)


def _public_clip(project_id: str, clip: dict[str, Any], *, compact: bool = False) -> dict[str, Any]:
    result = dict(clip)
    clip_id = clip["id"]
    render = clip.get("render") or {}
    ready = clip.get("render_status") == "ready"
    result["video_url"] = (
        f"/api/projects/{project_id}/clips/{clip_id}/media"
        if ready and render.get("video_file")
        else None
    )
    result["download_url"] = (
        f"/api/projects/{project_id}/clips/{clip_id}/download"
        if ready and render.get("video_file")
        else None
    )
    result["thumbnail_url"] = (
        f"/api/projects/{project_id}/clips/{clip_id}/poster"
        if ready and render.get("poster_file")
        else None
    )
    result["srt_url"] = (
        f"/api/projects/{project_id}/clips/{clip_id}/captions.srt"
        if ready and render.get("srt_file")
        else None
    )
    if compact:
        result.pop("transcript", None)
        result.pop("text", None)
        result.pop("features", None)
    return result


def _public_project(record: dict[str, Any], *, compact: bool = False) -> dict[str, Any]:
    result = dict(record)
    source = dict(result.get("source") or {})
    source.pop("stored_name", None)
    project_id = result["id"]
    source["source_url"] = f"/api/projects/{project_id}/source"
    source["thumbnail_url"] = (
        f"/api/projects/{project_id}/source-poster" if source.get("poster_file") else None
    )
    result["source"] = source
    result["clips"] = [
        _public_clip(project_id, clip, compact=compact) for clip in result.get("clips", [])
    ]
    result["ready_clip_count"] = sum(
        clip.get("render_status") == "ready" for clip in result.get("clips", [])
    )
    return result


def _safe_project(project_id: str) -> dict[str, Any]:
    try:
        return store.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proje bulunamadı") from exc


def _clip_file(project_id: str, clip_id: str, filename: str) -> Path:
    project = _safe_project(project_id)
    clip = _find_clip(project, clip_id)
    if clip.get("render_status") != "ready":
        raise HTTPException(status_code=404, detail="Klip çıktısı henüz hazır değil")
    artifact_key = _RENDER_ARTIFACT_KEYS.get(filename)
    render = clip.get("render") or {}
    if not artifact_key or render.get(artifact_key) != filename:
        raise HTTPException(status_code=404, detail="Klip çıktısı bulunamadı")
    directory = (store.project_dir(project_id) / "clips" / clip_id).resolve()
    expected_parent = (store.project_dir(project_id) / "clips").resolve()
    if directory.parent != expected_parent:
        raise HTTPException(status_code=400, detail="Geçersiz klip yolu")
    path = directory / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Klip çıktısı henüz hazır değil")
    return path


@app.get("/api/health")
def health() -> dict[str, Any]:
    disk = shutil.disk_usage(DATA_DIR)
    whisper = transcription_capability()
    ready = binary_available("ffmpeg") and binary_available("ffprobe")
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "device": "CPU · tamamen yerel",
        "gpu": False,
        "version": __version__,
        "local_only": True,
        "telemetry": False,
        "engine": {
            "ffmpeg": binary_available("ffmpeg"),
            "ffprobe": binary_available("ffprobe"),
            "transcription": whisper,
            "face_tracking": {
                "available": opencv_available(),
                "engine": "opencv" if opencv_available() else "center-crop",
            },
            "semantic_reranker": semantic_capability(),
        },
        "system": {
            "platform": platform.system(),
            "cpu_threads": os.cpu_count() or 1,
            "disk_total": disk.total,
            "disk_free": disk.free,
            "max_upload_bytes": MAX_UPLOAD_BYTES,
        },
    }


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    projects = store.list()
    total_size = 0
    for path in PROJECTS_DIR.rglob("*"):
        try:
            if path.is_file():
                total_size += path.stat().st_size
        except OSError:
            continue
    clip_count = sum(len(project.get("clips", [])) for project in projects)
    ready_clips = sum(
        sum(clip.get("render_status") == "ready" for clip in project.get("clips", []))
        for project in projects
    )
    processing_count = sum(
        project.get("status") in {"queued", "uploading", "processing"} for project in projects
    )
    completed_count = sum(project.get("status") == "completed" for project in projects)
    return {
        "projects": len(projects),
        "clips": clip_count,
        "ready_clips": ready_clips,
        "total_projects": len(projects),
        "total_clips": clip_count,
        "processing_projects": processing_count,
        "completed_projects": completed_count,
        "source_seconds": round(
            sum(float(project.get("source", {}).get("duration") or 0) for project in projects),
            1,
        ),
        "storage_bytes": total_size,
    }


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    return [_public_project(project, compact=True) for project in store.list()]


@app.post("/api/projects", status_code=status.HTTP_202_ACCEPTED)
async def create_project(
    file: UploadFile = File(...),
    settings: str = Form("{}"),
) -> dict[str, Any]:
    original_name = Path(file.filename or "video.mp4").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
        raise HTTPException(status_code=415, detail=f"Desteklenmeyen video türü. Desteklenenler: {allowed}")
    try:
        raw_settings = json.loads(settings)
        parsed_settings = ProjectSettings.model_validate(raw_settings)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Proje ayarları geçersiz: {exc}") from exc

    project_id = str(uuid.uuid4())
    stored_name = f"source{extension}"
    created = now_iso()
    display_name = (Path(original_name).stem or "Yeni proje")[:100]
    record: dict[str, Any] = {
        "id": project_id,
        "name": display_name,
        "status": "uploading",
        "stage": "upload",
        "progress": 0,
        "message": "Video yerel diske alınıyor",
        "error": None,
        "created_at": created,
        "updated_at": created,
        "settings": parsed_settings.model_dump(),
        "source": {
            "original_filename": original_name,
            "stored_name": stored_name,
            "size": 0,
        },
        "analysis": None,
        "stages": new_stages(),
        "clips": [],
    }
    store.create(record)
    destination = store.project_dir(project_id) / stored_name
    received = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                received += len(chunk)
                if received > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Video yükleme sınırını aşıyor ({MAX_UPLOAD_BYTES // 1024**3} GB)",
                    )
                handle.write(chunk)
        if received == 0:
            raise HTTPException(status_code=400, detail="Yüklenen video boş")
        metadata = await run_in_threadpool(probe_video, destination)
        if metadata["duration"] > MAX_VIDEO_SECONDS:
            raise HTTPException(
                status_code=413,
                detail=f"Video en fazla {MAX_VIDEO_SECONDS // 3600} saat olabilir",
            )

        def uploaded(item: dict[str, Any]) -> None:
            item["source"].update(metadata)
            item["source"]["size"] = received
            item.update(
                {
                    "status": "queued",
                    "stage": "prepare",
                    "progress": 1,
                    "message": "Analiz sırasına alındı",
                    "updated_at": now_iso(),
                }
            )

        project = store.update(project_id, uploaded)
        jobs.submit_analysis(project_id)
        return _public_project(project)
    except HTTPException:
        shutil.rmtree(store.project_dir(project_id), ignore_errors=True)
        raise
    except MediaError as exc:
        shutil.rmtree(store.project_dir(project_id), ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Video okunamadı: {exc}") from exc
    except Exception as exc:
        shutil.rmtree(store.project_dir(project_id), ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Video kaydedilemedi: {exc}") from exc
    finally:
        await file.close()


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    return _public_project(_safe_project(project_id))


@app.post("/api/projects/{project_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_project(project_id: str) -> dict[str, Any]:
    project = _safe_project(project_id)
    _ensure_project_idle(project, "Proje veya kliplerinden biri zaten işleniyor")

    def reset(record: dict[str, Any]) -> None:
        _ensure_project_idle(record, "Proje veya kliplerinden biri zaten işleniyor")
        record.update(
            {
                "status": "queued",
                "stage": "prepare",
                "progress": 1,
                "message": "Yeniden analiz sırasına alındı",
                "error": None,
                "stages": new_stages(),
                "updated_at": now_iso(),
            }
        )

    project = store.update(project_id, reset)
    jobs.submit_analysis(project_id)
    return _public_project(project)


@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str) -> None:
    project = _safe_project(project_id)
    _ensure_project_idle(project, "İşlenen proje silinemez; tamamlanmasını bekleyin")

    def mark_deleting(record: dict[str, Any]) -> None:
        _ensure_project_idle(record, "İşlenen proje silinemez; tamamlanmasını bekleyin")
        record.update(
            {
                "status": "processing",
                "stage": "delete",
                "message": "Proje yerel diskten siliniyor",
                "updated_at": now_iso(),
            }
        )

    store.update(project_id, mark_deleting)
    directory = store.delete(project_id)
    shutil.rmtree(directory)


@app.patch("/api/projects/{project_id}/clips/{clip_id}")
def update_clip(project_id: str, clip_id: str, update: ClipUpdate) -> dict[str, Any]:
    project = _safe_project(project_id)
    clip = _find_clip(project, clip_id)
    if clip.get("render_status") in _ACTIVE_RENDER_STATUSES:
        raise HTTPException(status_code=409, detail="Render sırasında klip değiştirilemez")
    changes = update.model_dump(exclude_none=True)
    start = float(changes.get("start", clip["start"]))
    end = float(changes.get("end", clip["end"]))
    source_duration = float(project["source"]["duration"])
    if end > source_duration + 0.001 or start >= end - 0.5:
        raise HTTPException(status_code=422, detail="Klip zaman aralığı kaynak videonun dışında")
    render_fields = {
        "start",
        "end",
        "aspect_ratio",
        "caption_preset",
        "enable_captions",
        "caption_color",
        "highlight_color",
        "font_size",
        "caption_position",
        "focus_x",
    }

    def mutate(record: dict[str, Any]) -> None:
        target = _find_clip(record, clip_id)
        if target.get("render_status") in _ACTIVE_RENDER_STATUSES:
            raise HTTPException(status_code=409, detail="Render sırasında klip değiştirilemez")
        target.update(changes)
        target["duration"] = round(float(target["end"]) - float(target["start"]), 3)
        target["updated_at"] = now_iso()
        if render_fields.intersection(changes):
            target["render_status"] = "stale"
            target["render_progress"] = 0
        record["updated_at"] = now_iso()

    updated = store.update(project_id, mutate)
    return _public_clip(project_id, _find_clip(updated, clip_id))


@app.post(
    "/api/projects/{project_id}/clips/{clip_id}/render",
    status_code=status.HTTP_202_ACCEPTED,
)
def render_project_clip(project_id: str, clip_id: str) -> dict[str, Any]:
    project = _safe_project(project_id)
    clip = _find_clip(project, clip_id)
    if clip.get("render_status") in _ACTIVE_RENDER_STATUSES:
        return _public_clip(project_id, clip)

    should_submit = [False]

    def queue_render(record: dict[str, Any]) -> None:
        if record.get("status") in _ACTIVE_PROJECT_STATUSES:
            raise HTTPException(status_code=409, detail="Proje analiz edilirken klip render edilemez")
        target = _find_clip(record, clip_id)
        if target.get("render_status") in _ACTIVE_RENDER_STATUSES:
            return
        target.update(
            {
                "render_status": "queued",
                "render_progress": 0,
                "render_error": None,
                "updated_at": now_iso(),
            }
        )
        record["updated_at"] = now_iso()
        should_submit[0] = True

    updated = store.update(project_id, queue_render)
    if should_submit[0]:
        jobs.submit_render(project_id, clip_id)
    return _public_clip(project_id, _find_clip(updated, clip_id))


@app.get("/api/projects/{project_id}/source")
def source_video(project_id: str) -> FileResponse:
    project = _safe_project(project_id)
    path = store.project_dir(project_id) / project["source"]["stored_name"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Kaynak video bulunamadı")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@app.get("/api/projects/{project_id}/source-poster")
def source_poster(project_id: str) -> FileResponse:
    project = _safe_project(project_id)
    filename = project.get("source", {}).get("poster_file")
    if not filename:
        raise HTTPException(status_code=404, detail="Kaynak görseli henüz hazır değil")
    path = store.project_dir(project_id) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Kaynak görseli bulunamadı")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/projects/{project_id}/clips/{clip_id}/media")
def clip_media(project_id: str, clip_id: str) -> FileResponse:
    path = _clip_file(project_id, clip_id, "clip.mp4")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/projects/{project_id}/clips/{clip_id}/download")
def clip_download(project_id: str, clip_id: str) -> FileResponse:
    project = _safe_project(project_id)
    clip = _find_clip(project, clip_id)
    path = _clip_file(project_id, clip_id, "clip.mp4")
    title = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in clip.get("title", "klip"))
    return FileResponse(path, media_type="video/mp4", filename=f"{title[:64] or 'klip'}.mp4")


@app.get("/api/projects/{project_id}/clips/{clip_id}/poster")
def clip_poster(project_id: str, clip_id: str) -> FileResponse:
    return FileResponse(_clip_file(project_id, clip_id, "poster.jpg"), media_type="image/jpeg")


@app.get("/api/projects/{project_id}/clips/{clip_id}/captions.srt")
def clip_captions(project_id: str, clip_id: str, download: bool = Query(default=True)) -> FileResponse:
    path = _clip_file(project_id, clip_id, "captions.srt")
    return FileResponse(
        path,
        media_type="application/x-subrip",
        filename="altyazilar.srt" if download else None,
    )


@app.get("/api")
def api_root() -> dict[str, str]:
    return {"name": "KlipForge Local", "version": __version__, "docs": "/api/docs"}


@app.get("/api/docs", response_class=HTMLResponse, include_in_schema=False)
def local_api_docs() -> str:
    return """<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KlipForge Local API</title><style>
body{max-width:900px;margin:0 auto;padding:42px 24px;background:#080b10;color:#f5f7fa;font:15px/1.6 system-ui,sans-serif}
h1{font-size:32px;margin-bottom:4px}p{color:#a6b0bf}a{color:#65e6b4}code{color:#9be9ca}
table{width:100%;border-collapse:collapse;margin:28px 0;background:#10151d}th,td{padding:11px 13px;border:1px solid #273140;text-align:left}th{color:#65e6b4}
.pill{display:inline-block;padding:3px 8px;border:1px solid #273140;border-radius:99px;color:#a6b0bf;font-size:12px}
</style></head><body><span class="pill">%100 yerel · v__VERSION__</span><h1>KlipForge Local API</h1>
<p>Bu sayfa dış CDN, font veya JavaScript kullanmaz. Makinece okunabilir tam şema: <a href="/api/openapi.json">/api/openapi.json</a>.</p>
<table><thead><tr><th>Yöntem</th><th>Yol</th><th>Açıklama</th></tr></thead><tbody>
<tr><td>GET</td><td><code>/api/health</code></td><td>Yerel motor ve model durumu</td></tr>
<tr><td>GET</td><td><code>/api/stats</code></td><td>Proje, klip ve depolama özeti</td></tr>
<tr><td>GET</td><td><code>/api/projects</code></td><td>Yerel projeleri listele</td></tr>
<tr><td>POST</td><td><code>/api/projects</code></td><td>Multipart video + settings ile proje oluştur</td></tr>
<tr><td>GET</td><td><code>/api/projects/{id}</code></td><td>Proje, ilerleme ve klipler</td></tr>
<tr><td>PATCH</td><td><code>/api/projects/{id}/clips/{clip_id}</code></td><td>Klip ayarlarını güncelle</td></tr>
<tr><td>POST</td><td><code>/api/projects/{id}/clips/{clip_id}/render</code></td><td>Yerel render başlat</td></tr>
</tbody></table><p>Sunucu varsayılan olarak yalnızca <code>127.0.0.1</code> üzerinde çalışır.</p></body></html>""".replace("__VERSION__", __version__)


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
def unknown_api(path: str) -> JSONResponse:
    return JSONResponse({"detail": f"API yolu bulunamadı: /api/{path}"}, status_code=404)


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    if FRONTEND_DIST.is_dir():
        requested = (FRONTEND_DIST / path).resolve()
        if requested.is_file() and FRONTEND_DIST.resolve() in requested.parents:
            return FileResponse(requested)
        index = FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index, media_type="text/html")
    return JSONResponse(
        {
            "detail": "Arayüz henüz derlenmedi. frontend klasöründe npm run build çalıştırın.",
            "api_docs": "/api/docs",
        },
        status_code=503,
    )
