from __future__ import annotations

import json
import os
import re
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from .config import PROJECTS_DIR


_SAFE_ID = re.compile(r"^[a-f0-9-]{32,36}$")


class ProjectStore:
    def __init__(self, root: Path = PROJECTS_DIR) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def project_dir(self, project_id: str) -> Path:
        if not _SAFE_ID.fullmatch(project_id):
            raise KeyError("Geçersiz proje kimliği")
        path = (self.root / project_id).resolve()
        if path.parent != self.root:
            raise KeyError("Geçersiz proje yolu")
        return path

    def metadata_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project.json"

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        project_id = str(record["id"])
        with self._lock:
            directory = self.project_dir(project_id)
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "clips").mkdir()
            (directory / "work").mkdir()
            (directory / "analysis").mkdir()
            self._write_unlocked(project_id, record)
        return deepcopy(record)

    def get(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            path = self.metadata_path(project_id)
            if not path.is_file():
                raise KeyError("Proje bulunamadı")
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

    def update(
        self,
        project_id: str,
        updater: Callable[[dict[str, Any]], None] | dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            record = self.get(project_id)
            if callable(updater):
                updater(record)
            else:
                record.update(updater)
            self._write_unlocked(project_id, record)
            return deepcopy(record)

    def list(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self._lock:
            for path in self.root.glob("*/project.json"):
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        records.append(json.load(handle))
                except (OSError, json.JSONDecodeError):
                    continue
        records.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return records

    def delete(self, project_id: str) -> Path:
        directory = self.project_dir(project_id)
        if not directory.is_dir():
            raise KeyError("Proje bulunamadı")
        return directory

    def _write_unlocked(self, project_id: str, record: dict[str, Any]) -> None:
        target = self.metadata_path(project_id)
        temporary = target.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
