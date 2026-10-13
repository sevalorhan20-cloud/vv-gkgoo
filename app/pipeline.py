from __future__ import annotations

import json
import shutil
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import WORKER_COUNT
from .media import MediaError, detect_scenes, extract_audio_energy, make_thumbnail, probe_video
from .reframe import detect_focus_x
from .render import render_clip
from .schemas import ProjectSettings
from .scoring import rank_highlight_candidates, select_diverse_highlights
from .semantic import rerank_with_local_ollama
from .store import ProjectStore
from .transcription import transcribe_video


STAGE_DEFINITIONS = [
    ("prepare", "Video hazırlanıyor"),
    ("transcribe", "Konuşma yazıya çevriliyor"),
    ("analyze", "Sahne ve ses sinyalleri inceleniyor"),
    ("score", "En güçlü anlar puanlanıyor"),
    ("render", "Dikey kadraj ve altyazılar hazırlanıyor"),
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_stages() -> list[dict[str, Any]]:
    return [
        {"key": key, "label": label, "status": "queued", "progress": 0, "detail": None}
        for key, label in STAGE_DEFINITIONS
    ]


class JobManager:
    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=WORKER_COUNT, thread_name_prefix="klipforge")
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()

    def recover_interrupted(self) -> None:
        for project in self.store.list():
            project_status = project.get("status")
            interrupted_clips = any(
                clip.get("render_status") in {"queued", "rendering"}
                for clip in project.get("clips", [])
            )
            if project_status not in {"uploading", "processing", "queued"} and not interrupted_clips:
                continue

            def recover(record: dict[str, Any]) -> None:
                timestamp = now_iso()
                if record.get("status") == "uploading":
                    record.update(
                        {
                            "status": "failed",
                            "message": "Yükleme uygulama kapanınca yarım kaldı",
                            "error": "Videoyu yeniden yükleyin veya bu yarım projeyi silin.",
                        }
                    )
                elif record.get("status") in {"processing", "queued"}:
                    record.update(
                        {
                            "status": "interrupted",
                            "message": "Uygulama yeniden başlatıldı. İşlemi tekrar başlatabilirsiniz.",
                            "error": None,
                        }
                    )
                for stage in record.get("stages", []):
                    if stage.get("status") == "running":
                        stage.update(
                            {
                                "status": "error",
                                "detail": "Uygulama yeniden başlatıldığı için adım kesildi",
                            }
                        )
                for clip in record.get("clips", []):
                    if clip.get("render_status") in {"queued", "rendering"}:
                        clip.update(
                            {
                                "render_status": "failed",
                                "render_progress": 0,
                                "render_error": "Render uygulama yeniden başlatıldığı için kesildi",
                                "updated_at": timestamp,
                            }
                        )
                record["updated_at"] = timestamp

            self.store.update(project["id"], recover)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def submit_analysis(self, project_id: str) -> None:
        key = f"analysis:{project_id}"
        with self._lock:
            existing = self._futures.get(key)
            if existing and not existing.done():
                return
            self._futures[key] = self.executor.submit(self._analyze_project, project_id)

    def submit_render(self, project_id: str, clip_id: str) -> None:
        key = f"render:{project_id}:{clip_id}"
        with self._lock:
            existing = self._futures.get(key)
            if existing and not existing.done():
                return
            self._futures[key] = self.executor.submit(self._render_one_clip_job, project_id, clip_id)

    def _set_stage(
        self,
        project_id: str,
        stage_key: str,
        *,
        status: str = "running",
        stage_progress: float = 0,
        overall_progress: float | None = None,
        detail: str | None = None,
    ) -> dict[str, Any]:
        def mutate(record: dict[str, Any]) -> None:
            for stage in record.get("stages", []):
                if stage["key"] == stage_key:
                    stage["status"] = status
                    stage["progress"] = int(round(max(0, min(1, stage_progress)) * 100))
                    if detail is not None:
                        stage["detail"] = detail
                elif status == "running" and stage["status"] == "running":
                    stage["status"] = "done"
                    stage["progress"] = 100
            record["stage"] = stage_key
            record["message"] = detail
            record["status"] = "processing"
            if overall_progress is not None:
                record["progress"] = int(round(max(0, min(1, overall_progress)) * 100))
            record["updated_at"] = now_iso()

        return self.store.update(project_id, mutate)

    def _finish_stage(self, project_id: str, stage_key: str, detail: str | None = None) -> None:
        def mutate(record: dict[str, Any]) -> None:
            for stage in record.get("stages", []):
                if stage["key"] == stage_key:
                    stage.update({"status": "done", "progress": 100})
                    if detail is not None:
                        stage["detail"] = detail
            record["updated_at"] = now_iso()

        self.store.update(project_id, mutate)

    def _fail_project(self, project_id: str, exc: Exception) -> None:
        message = str(exc).strip() or exc.__class__.__name__

        def mutate(record: dict[str, Any]) -> None:
            record.update(
                {
                    "status": "failed",
                    "error": message[:1200],
                    "message": "İşlem tamamlanamadı",
                    "updated_at": now_iso(),
                }
            )
            for stage in record.get("stages", []):
                if stage["status"] == "running":
                    stage["status"] = "error"
                    stage["detail"] = message[:300]

        try:
            self.store.update(project_id, mutate)
        except KeyError:
            pass

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _analyze_project(self, project_id: str) -> None:
        try:
            project = self.store.get(project_id)
            project_dir = self.store.project_dir(project_id)
            source = project_dir / project["source"]["stored_name"]
            settings = ProjectSettings.model_validate(project["settings"])
            work_dir = project_dir / "work"
            analysis_dir = project_dir / "analysis"
            clips_dir = project_dir / "clips"
            shutil.rmtree(work_dir, ignore_errors=True)
            shutil.rmtree(clips_dir, ignore_errors=True)
            work_dir.mkdir(parents=True, exist_ok=True)
            clips_dir.mkdir(parents=True, exist_ok=True)

            self.store.update(
                project_id,
                lambda record: record.update(
                    {
                        "status": "processing",
                        "progress": 1,
                        "error": None,
                        "message": "Video hazırlanıyor",
                        "updated_at": now_iso(),
                        "stages": new_stages(),
                        "clips": [],
                    }
                ),
            )
            self._set_stage(project_id, "prepare", overall_progress=0.03, detail="Video bilgileri doğrulanıyor")
            metadata = probe_video(source)
            poster = project_dir / "source-poster.jpg"
            make_thumbnail(source, poster, min(2.0, metadata["duration"] * 0.12))
            self.store.update(
                project_id,
                lambda record: record["source"].update(
                    {
                        **metadata,
                        "poster_file": poster.name,
                    }
                ),
            )
            self._finish_stage(project_id, "prepare", "Kaynak video hazır")

            transcript: list[dict[str, Any]] = []
            transcription_info: dict[str, Any] = {"engine": "skipped", "reason": "Videoda ses yok"}
            if metadata.get("has_audio"):
                self._set_stage(
                    project_id,
                    "transcribe",
                    overall_progress=0.12,
                    detail="Yerel konuşma modeli çalıştırılıyor",
                )

                last_transcription_progress = [-1.0]

                def transcription_progress(value: float) -> None:
                    if value < 1.0 and value - last_transcription_progress[0] < 0.025:
                        return
                    last_transcription_progress[0] = value
                    self._set_stage(
                        project_id,
                        "transcribe",
                        stage_progress=value,
                        overall_progress=0.12 + 0.28 * value,
                        detail="Konuşma yerel olarak çözümleniyor",
                    )

                transcript, transcription_info = transcribe_video(
                    source,
                    language=settings.language,
                    progress=transcription_progress,
                )
                transcription_detail = (
                    f"{len(transcript)} konuşma bölümü bulundu"
                    if transcript
                    else "Yerel model yok; ses ve görüntü analiziyle devam edildi"
                )
                self._finish_stage(project_id, "transcribe", transcription_detail)
            else:
                self._set_stage(
                    project_id,
                    "transcribe",
                    status="done",
                    stage_progress=1,
                    overall_progress=0.40,
                    detail="Sessiz video; bu adım atlandı",
                )
            self._write_json(analysis_dir / "transcript.json", transcript)

            self._set_stage(
                project_id,
                "analyze",
                overall_progress=0.42,
                detail="Ses ritmi ve sahne geçişleri taranıyor",
            )
            if metadata.get("has_audio"):
                energy, energy_step = extract_audio_energy(source, work_dir)
            else:
                energy, energy_step = [], 0.5
            self._set_stage(
                project_id,
                "analyze",
                stage_progress=0.52,
                overall_progress=0.49,
                detail="Görsel sahne değişimleri aranıyor",
            )
            scenes = detect_scenes(source, settings.scene_sensitivity)
            self._write_json(
                analysis_dir / "signals.json",
                {
                    "energy_step": energy_step,
                    "energy": energy,
                    "scenes": scenes,
                },
            )
            self._finish_stage(project_id, "analyze", f"{len(scenes)} sahne geçişi incelendi")

            self._set_stage(
                project_id,
                "score",
                overall_progress=0.56,
                detail="Aday anlar açıklanabilir sinyallerle sıralanıyor",
            )
            ranked_candidates = rank_highlight_candidates(
                metadata["duration"],
                transcript,
                energy,
                energy_step,
                scenes,
                settings,
            )
            # Keep a wider, already-diverse pool so the optional semantic pass can
            # rescue a strong moment that the lightweight heuristic ranked lower.
            candidate_pool = select_diverse_highlights(
                ranked_candidates,
                min_score=0,
                clip_count=max(10, settings.clip_count),
                decorate=False,
            )
            candidate_pool, semantic_info = rerank_with_local_ollama(candidate_pool, settings)
            highlights = select_diverse_highlights(
                candidate_pool,
                min_score=settings.min_score,
                clip_count=settings.clip_count,
            )
            analysis_summary = {
                "transcript_file": "analysis/transcript.json",
                "signals_file": "analysis/signals.json",
                "transcription": transcription_info,
                "scene_count": len(scenes),
                "clip_count": len(highlights),
                "score_method": "local-explainable-v1",
                "semantic": semantic_info,
                "trend_data": None,
            }
            if not highlights:
                self.store.update(
                    project_id,
                    lambda record: record.update(
                        {"clips": [], "analysis": analysis_summary, "updated_at": now_iso()}
                    ),
                )
                self._finish_stage(
                    project_id,
                    "score",
                    f"{settings.min_score}+ puan eşiğini geçen an bulunamadı",
                )
                self._set_stage(
                    project_id,
                    "render",
                    status="done",
                    stage_progress=1,
                    overall_progress=1,
                    detail="Hazırlanacak klip yok",
                )
                self.store.update(
                    project_id,
                    lambda record: record.update(
                        {
                            "status": "completed",
                            "stage": "complete",
                            "progress": 100,
                            "message": "Seçilen puan eşiğine uyan an bulunamadı",
                            "error": None,
                            "updated_at": now_iso(),
                        }
                    ),
                )
                shutil.rmtree(work_dir, ignore_errors=True)
                work_dir.mkdir(exist_ok=True)
                return
            clips: list[dict[str, Any]] = []
            for highlight in highlights:
                clip_id = uuid.uuid4().hex
                focus = (
                    detect_focus_x(source, highlight["start"], highlight["end"])
                    if settings.auto_reframe
                    else {"focus_x": 0.5, "engine": "center", "detections": 0}
                )
                clips.append(
                    {
                        "id": clip_id,
                        **highlight,
                        "aspect_ratio": settings.aspect_ratio,
                        "caption_preset": settings.caption_preset,
                        "enable_captions": settings.enable_captions,
                        "caption_color": "#FFFFFF",
                        "highlight_color": "#65E6B4",
                        "font_size": None,
                        "caption_position": "bottom",
                        "focus_x": focus["focus_x"],
                        "reframe": focus,
                        "render_status": "queued",
                        "render_progress": 0,
                        "render": None,
                        "favorite": False,
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                )
            self.store.update(
                project_id,
                lambda record: record.update(
                    {
                        "clips": clips,
                        "analysis": {**analysis_summary, "clip_count": len(clips)},
                        "updated_at": now_iso(),
                    }
                ),
            )
            self._finish_stage(project_id, "score", f"{len(clips)} güçlü an seçildi")

            self._set_stage(
                project_id,
                "render",
                overall_progress=0.65,
                detail="Klipler sırayla hazırlanıyor",
            )
            successful = 0
            for index, clip in enumerate(clips):
                try:
                    self._render_clip(project_id, clip["id"], transcript, source, metadata, index, len(clips))
                    successful += 1
                except Exception as exc:
                    self._update_clip(
                        project_id,
                        clip["id"],
                        {
                            "render_status": "failed",
                            "render_error": str(exc)[:500],
                            "updated_at": now_iso(),
                        },
                    )
            if not successful:
                raise MediaError("Seçilen klipler render edilemedi")
            self._finish_stage(project_id, "render", f"{successful} klip hazır")

            def complete(record: dict[str, Any]) -> None:
                record.update(
                    {
                        "status": "completed",
                        "stage": "complete",
                        "progress": 100,
                        "message": f"Bağlamı korunmuş {successful} an hazır",
                        "error": None,
                        "updated_at": now_iso(),
                    }
                )

            self.store.update(project_id, complete)
            shutil.rmtree(work_dir, ignore_errors=True)
            work_dir.mkdir(exist_ok=True)
        except Exception as exc:
            self._fail_project(project_id, exc)

    def _update_clip(self, project_id: str, clip_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        selected: dict[str, Any] = {}

        def mutate(record: dict[str, Any]) -> None:
            for clip in record.get("clips", []):
                if clip["id"] == clip_id:
                    clip.update(changes)
                    selected.update(clip)
                    record["updated_at"] = now_iso()
                    return
            raise KeyError("Klip bulunamadı")

        self.store.update(project_id, mutate)
        return selected

    def _render_clip(
        self,
        project_id: str,
        clip_id: str,
        transcript: list[dict[str, Any]],
        source: Path,
        metadata: dict[str, Any],
        index: int = 0,
        total: int = 1,
        update_project_progress: bool = True,
    ) -> dict[str, Any]:
        project = self.store.get(project_id)
        clip = next((item for item in project.get("clips", []) if item["id"] == clip_id), None)
        if not clip:
            raise KeyError("Klip bulunamadı")
        self._update_clip(project_id, clip_id, {"render_status": "rendering", "render_progress": 0, "render_error": None})
        output_dir = self.store.project_dir(project_id) / "clips" / clip_id

        def progress(value: float) -> None:
            self._update_clip(
                project_id,
                clip_id,
                {"render_status": "rendering", "render_progress": int(round(value * 100))},
            )
            if update_project_progress:
                overall = 0.65 + 0.34 * ((index + value) / max(1, total))
                self._set_stage(
                    project_id,
                    "render",
                    stage_progress=(index + value) / max(1, total),
                    overall_progress=overall,
                    detail=f"Klip {index + 1}/{total} hazırlanıyor",
                )

        result = render_clip(source, output_dir, clip, metadata, transcript, progress)
        return self._update_clip(
            project_id,
            clip_id,
            {
                "render_status": "ready",
                "render_progress": 100,
                "render_error": None,
                "render": result,
                "updated_at": now_iso(),
            },
        )

    def _render_one_clip_job(self, project_id: str, clip_id: str) -> None:
        try:
            project = self.store.get(project_id)
            project_dir = self.store.project_dir(project_id)
            source = project_dir / project["source"]["stored_name"]
            transcript = self._read_json(project_dir / "analysis" / "transcript.json", [])
            metadata = {key: value for key, value in project["source"].items() if key not in {"stored_name"}}
            self._render_clip(
                project_id,
                clip_id,
                transcript,
                source,
                metadata,
                update_project_progress=False,
            )
            # A manual render should not push a completed project back into processing.
            self.store.update(
                project_id,
                lambda record: record.update(
                    {
                        "status": "completed",
                        "stage": "complete",
                        "progress": 100,
                        "message": "Klip güncellendi",
                        "updated_at": now_iso(),
                    }
                ),
            )
        except Exception as exc:
            try:
                self._update_clip(
                    project_id,
                    clip_id,
                    {"render_status": "failed", "render_error": str(exc)[:500], "updated_at": now_iso()},
                )
            except KeyError:
                pass
