from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from app import semantic
from app.schemas import ProjectSettings
from app.scoring import select_diverse_highlights


def _clip(score: int = 70) -> dict[str, Any]:
    return {
        "start": 0.0,
        "end": 20.0,
        "duration": 20.0,
        "text": "Nasıl daha iyi bir sonuç alınır? İşte önemli yöntem.",
        "score": score,
        "confidence": 0.82,
        "breakdown": {"hook": score, "flow": score, "value": score, "trend": None},
        "reasons": ["Heuristik neden"],
    }


class _StubResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _StubOpener:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def open(self, request: object, timeout: int) -> _StubResponse:
        return _StubResponse(self.payload)


def _stub_ollama(monkeypatch: pytest.MonkeyPatch, response: Any) -> None:
    monkeypatch.setattr(semantic, "OLLAMA_MODEL", "local-test-model")
    monkeypatch.setattr(semantic, "OLLAMA_URL", "http://127.0.0.1:11434")
    outer = {"response": json.dumps(response)}
    monkeypatch.setattr(
        semantic.urllib.request,
        "build_opener",
        lambda *args: _StubOpener(outer),
    )


def test_malformed_null_clips_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [_clip()]
    original = copy.deepcopy(clips)
    _stub_ollama(monkeypatch, {"clips": None})

    result, info = semantic.rerank_with_local_ollama(clips, ProjectSettings())

    assert result == original
    assert info["engine"] == "failed"


def test_partial_semantic_scores_are_not_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [_clip()]
    _stub_ollama(
        monkeypatch,
        {"clips": [{"id": 0, "hook": 99, "flow": 99, "title": "Eksik skor"}]},
    )

    result, info = semantic.rerank_with_local_ollama(clips, ProjectSettings())

    assert result[0]["score"] == 70
    assert "semantic_engine" not in result[0]
    assert info["engine"] == "ollama"
    assert info["applied"] == 0


def test_minimum_score_is_reapplied_after_semantic_rerank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clips = [_clip(score=70)]
    _stub_ollama(
        monkeypatch,
        {"clips": [{"id": 0, "hook": 0, "flow": 0, "value": 0}]},
    )

    reranked, info = semantic.rerank_with_local_ollama(
        clips,
        ProjectSettings(min_score=70, clip_count=1),
    )
    selected = select_diverse_highlights(reranked, min_score=70, clip_count=1)

    assert info["applied"] == 1
    assert reranked[0]["score"] < 70
    assert selected == []
