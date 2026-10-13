from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import OLLAMA_MODEL, OLLAMA_URL
from .schemas import ProjectSettings


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Keep transcript-bearing Ollama requests on the validated loopback URL."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise urllib.error.HTTPError(
            req.full_url,
            code,
            "Ollama yönlendirmeleri güvenlik nedeniyle reddedildi",
            headers,
            fp,
        )


def _local_ollama_url() -> str | None:
    if not OLLAMA_MODEL or not OLLAMA_URL:
        return None
    parsed = urllib.parse.urlparse(OLLAMA_URL)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        return None
    return OLLAMA_URL


def semantic_capability() -> dict[str, Any]:
    return {
        "configured": _local_ollama_url() is not None,
        "model": OLLAMA_MODEL or None,
        "local_endpoint": _local_ollama_url(),
    }


def _bounded_score(value: Any) -> int | None:
    try:
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return int(round(max(0.0, min(99.0, numeric))))
    except (TypeError, ValueError, OverflowError):
        return None


def _extract_json(value: str) -> Any:
    value = value.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def rerank_with_local_ollama(
    clips: list[dict[str, Any]],
    settings: ProjectSettings,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_url = _local_ollama_url()
    if not base_url:
        return clips, {"engine": "disabled"}
    eligible = [clip for clip in clips if clip.get("text")][:10]
    if not eligible:
        return clips, {"engine": "skipped", "reason": "Transkript yok"}
    candidate_payload = [
        {
            "id": index,
            "start": clip["start"],
            "end": clip["end"],
            "heuristic_score": clip["score"],
            "transcript": str(clip.get("text", ""))[:1800],
        }
        for index, clip in enumerate(eligible)
    ]
    prompt = f"""You are a short-form video editor. Score each candidate only from its transcript.
Goal: {settings.goal}. User focus: {settings.prompt or 'best self-contained moments'}.
Return strict JSON with this shape: {{"clips":[{{"id":0,"hook":0,"flow":0,"value":0,"title":"...","reasons":["...","..."]}}]}}.
Scores are integers 0-99. Hook means opening strength, Flow means standalone coherence, Value means useful/emotional payoff.
Do not invent a live trend score. Titles must be concise and in the transcript language. Reasons must be short and evidence-based.
Candidates:
{json.dumps(candidate_payload, ensure_ascii=False)}"""
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        # Never route a local transcript through an inherited HTTP proxy.
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _RejectRedirects(),
        )
        with opener.open(request, timeout=180) as response:
            outer = json.loads(response.read().decode("utf-8"))
        if not isinstance(outer, dict):
            raise ValueError("Ollama yanıt zarfı nesne değil")
        parsed = _extract_json(str(outer.get("response", "")))
        if not isinstance(parsed, dict):
            raise ValueError("Ollama klip yanıtı nesne değil")
        rows = parsed.get("clips", [])
        if not isinstance(rows, list):
            raise ValueError("Ollama clips alanı liste değil")
        by_id = {int(row.get("id")): row for row in rows if isinstance(row, dict) and str(row.get("id", "")).isdigit()}
        planned_updates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for index, clip in enumerate(eligible):
            row = by_id.get(index)
            if not row:
                continue
            hook = _bounded_score(row.get("hook"))
            flow = _bounded_score(row.get("flow"))
            value = _bounded_score(row.get("value"))
            if hook is None or flow is None or value is None:
                continue
            semantic_overall = (hook + flow + value) / 3
            previous_breakdown = clip.get("breakdown")
            if not isinstance(previous_breakdown, dict):
                previous_breakdown = {}
            breakdown = dict(previous_breakdown)
            breakdown["hook"] = int(round(0.4 * float(previous_breakdown.get("hook", hook)) + 0.6 * hook))
            breakdown["flow"] = int(round(0.4 * float(previous_breakdown.get("flow", flow)) + 0.6 * flow))
            previous_value = previous_breakdown.get("value")
            breakdown["value"] = value if previous_value is None else int(round(0.4 * float(previous_value) + 0.6 * value))
            changes: dict[str, Any] = {
                "score": int(round(0.45 * float(clip["score"]) + 0.55 * semantic_overall)),
                "breakdown": breakdown,
                "semantic_engine": OLLAMA_MODEL,
                "confidence": min(0.95, max(float(clip.get("confidence", 0.5)), 0.78)),
            }
            title = str(row.get("title", "")).strip()
            if title:
                changes["title"] = title[:100]
            reasons = row.get("reasons")
            if isinstance(reasons, list):
                cleaned = [str(reason).strip()[:160] for reason in reasons if str(reason).strip()]
                if cleaned:
                    changes["reasons"] = cleaned[:3]
            planned_updates.append((clip, changes))
        for clip, changes in planned_updates:
            clip.update(changes)
        clips.sort(key=lambda item: (item["score"], item.get("confidence", 0)), reverse=True)
        for rank, clip in enumerate(clips, start=1):
            clip["rank"] = rank
        return clips, {
            "engine": "ollama",
            "model": OLLAMA_MODEL,
            "candidates": len(eligible),
            "applied": len(planned_updates),
        }
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ) as exc:
        return clips, {"engine": "failed", "model": OLLAMA_MODEL, "reason": str(exc)[:300]}
