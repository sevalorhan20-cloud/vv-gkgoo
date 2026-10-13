from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from app import store as store_module
from app.store import ProjectStore


@pytest.mark.parametrize(
    "unsafe_id",
    [
        "",
        "abc",
        "../" + "a" * 32,
        "a" * 32 + "/child",
        "A" * 32,
        "%2e%2e",
        "g" * 32,
    ],
)
def test_project_paths_reject_unsafe_ids(tmp_path: Path, unsafe_id: str) -> None:
    store = ProjectStore(tmp_path / "projects")

    with pytest.raises(KeyError, match="Geçersiz"):
        store.project_dir(unsafe_id)


def test_project_path_for_valid_id_stays_directly_under_root(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    project_id = uuid.uuid4().hex

    resolved = store.project_dir(project_id)

    assert resolved.parent == store.root
    assert resolved.name == project_id


def test_update_writes_complete_json_via_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ProjectStore(tmp_path / "projects")
    project_id = uuid.uuid4().hex
    original = {"id": project_id, "name": "İlk", "progress": 0, "nested": {"ok": True}}
    store.create(original)

    real_replace = os.replace
    replacements: list[tuple[Path, Path, dict[str, object]]] = []

    def tracked_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        source_path = Path(source)
        target_path = Path(target)
        replacements.append(
            (
                source_path,
                target_path,
                json.loads(source_path.read_text(encoding="utf-8")),
            )
        )
        real_replace(source, target)

    monkeypatch.setattr(store_module.os, "replace", tracked_replace)

    updated = store.update(
        project_id,
        lambda record: record.update({"name": "Güncel", "progress": 100}),
    )

    target = store.metadata_path(project_id)
    temporary = target.with_suffix(".json.tmp")
    assert updated["name"] == "Güncel"
    assert len(replacements) == 1
    assert replacements[0][0] == temporary
    assert replacements[0][1] == target
    assert replacements[0][2]["progress"] == 100
    assert not temporary.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == updated


def test_failed_updater_does_not_partially_persist_record(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    project_id = uuid.uuid4().hex
    store.create({"id": project_id, "status": "queued"})

    def fail_after_mutation(record: dict[str, object]) -> None:
        record["status"] = "corrupt"
        raise RuntimeError("planned failure")

    with pytest.raises(RuntimeError, match="planned failure"):
        store.update(project_id, fail_after_mutation)

    assert store.get(project_id)["status"] == "queued"
    assert not store.metadata_path(project_id).with_suffix(".json.tmp").exists()
