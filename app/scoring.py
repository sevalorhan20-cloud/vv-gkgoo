from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import numpy as np

from .schemas import ProjectSettings


HOOK_TERMS = {
    "nasıl",
    "neden",
    "asla",
    "gerçek",
    "sır",
    "hata",
    "şaşırtıcı",
    "işte",
    "bakın",
    "düşünün",
    "what",
    "why",
    "how",
    "never",
    "secret",
    "mistake",
    "truth",
    "imagine",
    "listen",
}
VALUE_TERMS = {
    "çünkü",
    "yöntem",
    "adım",
    "örnek",
    "sonuç",
    "öğren",
    "fayda",
    "önemli",
    "taktik",
    "because",
    "method",
    "step",
    "example",
    "result",
    "learn",
    "important",
    "strategy",
    "tip",
}
GOAL_TERMS = {
    "education": VALUE_TERMS | {"ders", "özet", "anlamak", "explain", "guide"},
    "podcast": {"bence", "hikaye", "sence", "anlat", "think", "story", "feel"},
    "gaming": {"oyun", "kazandım", "boss", "kill", "win", "game", "level"},
    "viral": HOOK_TERMS | {"inanılmaz", "wow", "amazing"},
    "custom": set(),
}

MAX_DIVERSITY_IOU = 0.20
MAX_DIVERSITY_CONTAINMENT = 0.35


@dataclass(frozen=True)
class Candidate:
    start: float
    end: float
    text: str
    transcript: list[dict[str, Any]]


def _clamp(value: float, low: float = 0.0, high: float = 99.0) -> int:
    return int(round(min(high, max(low, value))))


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    # Unicode case-folding represents Turkish capital İ as ``i`` + combining dot.
    # Collapse that sequence so words such as "İşte" remain a single token.
    normalized = unicodedata.normalize("NFKC", normalized.replace("i\u0307", "i"))
    return re.findall(r"[\wğüşöçı'-]+", normalized, flags=re.UNICODE)


def _energy_slice(
    energy: list[float],
    step: float,
    start: float,
    end: float,
) -> np.ndarray:
    if not energy or step <= 0:
        return np.asarray([], dtype=np.float32)
    left = max(0, int(start / step))
    right = min(len(energy), max(left + 1, int(math.ceil(end / step))))
    return np.asarray(energy[left:right], dtype=np.float32)


def _overlap_ratios(
    left: tuple[float, float],
    right: tuple[float, float],
) -> tuple[float, float]:
    intersection = max(0.0, min(left[1], right[1]) - max(left[0], right[0]))
    union = max(left[1], right[1]) - min(left[0], right[0])
    shorter = min(max(0.0, left[1] - left[0]), max(0.0, right[1] - right[0]))
    iou = intersection / union if union > 0 else 0.0
    containment = intersection / shorter if shorter > 0 else 0.0
    return iou, containment


def _segments_within_interval(
    segments: list[dict[str, Any]],
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    tolerance = 0.01
    return [
        item
        for item in segments
        if float(item.get("start", 0)) >= start - tolerance
        and float(item.get("end", 0)) <= end + tolerance
        and float(item.get("end", 0)) > float(item.get("start", 0))
    ]


def _candidate_text(segments: list[dict[str, Any]]) -> str:
    return " ".join(str(item.get("text", "")).strip() for item in segments).strip()


def _candidate_from_transcript(
    segments: list[dict[str, Any]],
    index: int,
    min_duration: float,
    max_duration: float,
    duration: float,
) -> Candidate | None:
    start = max(0.0, float(segments[index]["start"]) - 0.2)
    if duration - start + 0.01 < min_duration:
        return None
    minimum_end = start + min_duration
    target_end = start + min(max_duration, max(min_duration, (min_duration + max_duration) / 2))
    maximum_end = min(duration, start + max_duration)
    eligible: list[tuple[float, int, bool]] = []
    for cursor in range(index, len(segments)):
        end = min(duration, float(segments[cursor]["end"]) + 0.15)
        if end + 0.01 < minimum_end:
            continue
        if end > maximum_end + 0.01:
            break
        text = str(segments[cursor].get("text", "")).strip()
        complete = bool(re.search(r"[.!?…]['\"]?$", text))
        distance = abs(end - target_end) - (3.0 if complete else 0.0)
        eligible.append((distance, cursor, complete))
    if not eligible:
        end = min(duration, maximum_end)
        if end - start + 0.01 >= min_duration:
            selected = _segments_within_interval(segments[index:], start, end)
            if selected:
                return Candidate(start, end, _candidate_text(selected), selected)
        return None
    _, end_index, _ = min(eligible, key=lambda item: item[0])
    end = min(duration, float(segments[end_index]["end"]) + 0.15)
    selected = _segments_within_interval(segments[index : end_index + 1], start, end)
    if not selected or end - start + 0.01 < min_duration:
        return None
    return Candidate(start, end, _candidate_text(selected), selected)


def _generate_candidates(
    duration: float,
    transcript: list[dict[str, Any]],
    energy: list[float],
    energy_step: float,
    scenes: list[float],
    settings: ProjectSettings,
) -> list[Candidate]:
    minimum = min(settings.min_duration, duration)
    maximum = min(settings.max_duration, duration)
    if duration <= maximum + 0.01:
        chosen = _segments_within_interval(transcript, 0.0, duration)
        return [Candidate(0.0, duration, _candidate_text(chosen), chosen)]

    candidates: list[Candidate] = []
    if transcript:
        for index in range(len(transcript)):
            # Dense enough for coverage, bounded enough for long recordings.
            if index > 0 and index % 2 and len(transcript) > 80:
                continue
            candidate = _candidate_from_transcript(
                transcript,
                index,
                minimum,
                maximum,
                duration,
            )
            if candidate:
                candidates.append(candidate)
    else:
        target = min(maximum, max(minimum, (minimum + maximum) / 2))
        stride = max(4.0, target / 5)
        starts = list(np.arange(0, max(0.1, duration - target + 0.1), stride))
        starts.extend(max(0.0, point - target * 0.22) for point in scenes)
        if energy and energy_step > 0:
            arr = np.asarray(energy, dtype=np.float32)
            width = max(1, int(target / energy_step))
            if arr.size >= width:
                rolling = np.convolve(arr, np.ones(width, dtype=np.float32) / width, mode="valid")
                peak_count = min(30, max(settings.clip_count * 5, 10), rolling.size)
                for index in np.argpartition(rolling, -peak_count)[-peak_count:]:
                    starts.append(float(index) * energy_step)
        for start in sorted(set(round(float(x), 2) for x in starts)):
            start = min(max(0.0, start), max(0.0, duration - minimum))
            end = min(duration, start + target)
            if end - start + 0.01 >= minimum:
                candidates.append(Candidate(start, end, "", []))
    # Remove exact/near duplicates before the heavier scoring pass.
    deduplicated: list[Candidate] = []
    for item in sorted(candidates, key=lambda c: (c.start, c.end)):
        if not deduplicated or abs(item.start - deduplicated[-1].start) > 0.75 or abs(item.end - deduplicated[-1].end) > 0.75:
            deduplicated.append(item)
    return deduplicated


def _opening_text(candidate: Candidate, seconds: float = 5.0) -> str:
    window_end = min(candidate.end, candidate.start + seconds)
    parts: list[str] = []
    for segment in candidate.transcript:
        segment_start = float(segment.get("start", 0))
        segment_end = float(segment.get("end", 0))
        if segment_start >= window_end:
            break
        if segment_end <= candidate.start:
            continue
        words = segment.get("words") or []
        if words:
            parts.extend(
                str(word.get("text", "")).strip()
                for word in words
                if float(word.get("end", 0)) > candidate.start
                and float(word.get("start", 0)) < window_end
                and str(word.get("text", "")).strip()
            )
        else:
            text = str(segment.get("text", "")).strip()
            if text:
                parts.append(text)
    return " ".join(parts).strip()


def _score_candidate(
    candidate: Candidate,
    energy: list[float],
    energy_step: float,
    scenes: list[float],
    settings: ProjectSettings,
) -> dict[str, Any]:
    values = _energy_slice(energy, energy_step, candidate.start, candidate.end)
    early = _energy_slice(energy, energy_step, candidate.start, min(candidate.end, candidate.start + 4))
    edge_start = _energy_slice(energy, energy_step, candidate.start, min(candidate.end, candidate.start + 0.8))
    edge_end = _energy_slice(energy, energy_step, max(candidate.start, candidate.end - 0.8), candidate.end)
    mean_energy = float(values.mean()) if values.size else 0.5
    dynamic_energy = float(values.std()) if values.size else 0.25
    early_energy = float(early.mean()) if early.size else mean_energy
    boundary_quality = 1 - min(1.0, ((float(edge_start.mean()) if edge_start.size else 0.5) + (float(edge_end.mean()) if edge_end.size else 0.5)) / 2)
    scene_count = sum(candidate.start <= point <= candidate.end for point in scenes)
    scene_rate = min(1.0, scene_count / max(1.0, (candidate.end - candidate.start) / 12))

    tokens = _tokens(candidate.text)
    token_set = set(tokens)
    opening_text = _opening_text(candidate)
    opening_tokens = _tokens(opening_text)
    opening = " ".join(opening_tokens[:18])
    hook_hits = len(set(opening_tokens) & HOOK_TERMS)
    goal_hits = len(token_set & GOAL_TERMS.get(settings.goal, set()))
    prompt_tokens = set(_tokens(settings.prompt))
    prompt_hits = len(token_set & prompt_tokens) if prompt_tokens else 0
    has_number = bool(re.search(r"\d", candidate.text))
    opening_has_number = bool(re.search(r"\d", opening_text))
    has_question = "?" in opening_text or any(
        opening == term or opening.startswith(term + " ")
        for term in {"nasıl", "neden", "what", "why", "how"}
    )
    complete_end = bool(re.search(r"[.!?…]['\"]?$", candidate.text.strip())) if candidate.text else False
    speech_duration = sum(
        max(0.0, min(candidate.end, float(item.get("end", 0))) - max(candidate.start, float(item.get("start", 0))))
        for item in candidate.transcript
    )
    speech_density = min(1.0, speech_duration / max(1.0, candidate.end - candidate.start)) if candidate.transcript else None

    hook = 38 + 26 * early_energy + 12 * min(1, hook_hits) + 7 * has_question + 4 * opening_has_number + 5 * scene_rate
    if candidate.text and len(tokens) < 8:
        hook -= 8
    flow = 42 + 20 * boundary_quality + 14 * dynamic_energy + 8 * scene_rate
    if speech_density is not None:
        flow += 11 * speech_density + (5 if complete_end else -4)
    value: int | None
    if tokens:
        unique_ratio = len(set(tokens)) / max(1, len(tokens))
        value_hits = len(token_set & VALUE_TERMS) + goal_hits
        information_density = min(1.0, len(tokens) / max(25.0, (candidate.end - candidate.start) * 2.0))
        value = _clamp(
            35
            + 14 * min(1.0, value_hits / 2)
            + 13 * unique_ratio
            + 13 * information_density
            + 7 * has_number
            + 6 * complete_end
            + 8 * min(1.0, prompt_hits / max(1, len(prompt_tokens)))
        )
    else:
        value = None

    hook_score = _clamp(hook)
    flow_score = _clamp(flow)
    components: list[tuple[float, float]] = [(hook_score, 0.38), (flow_score, 0.30)]
    if value is not None:
        components.append((value, 0.32))
    overall = _clamp(sum(score * weight for score, weight in components) / sum(weight for _, weight in components))

    reasons: list[str] = []
    if has_question or hook_hits:
        reasons.append("İlk saniyelerde güçlü bir merak kancası var")
    elif early_energy >= 0.58:
        reasons.append("Yüksek enerjili ve hızlı bir giriş yapıyor")
    if value is not None and value >= 68:
        reasons.append("Bilgi ve çıkarım yoğunluğu yüksek")
    if complete_end:
        reasons.append("Fikir klip içinde doğal biçimde tamamlanıyor")
    if scene_rate >= 0.55:
        reasons.append("Görsel tempo dikkati canlı tutuyor")
    if prompt_hits:
        reasons.append("İstediğiniz konuya doğrudan uyuyor")
    if not reasons:
        reasons.append("Ses temposu ve doğal sınırlar dengeli")
    reasons = reasons[:3]

    return {
        "start": round(candidate.start, 3),
        "end": round(candidate.end, 3),
        "duration": round(candidate.end - candidate.start, 3),
        "text": candidate.text,
        "transcript": candidate.transcript,
        "score": overall,
        "score_label": "Öne çıkma tahmini",
        "breakdown": {
            "hook": hook_score,
            "flow": flow_score,
            "value": value,
            "trend": None,
        },
        "confidence": round(0.82 if candidate.transcript else 0.58, 2),
        "reasons": reasons,
        "features": {
            "mean_energy": round(mean_energy, 4),
            "energy_dynamics": round(dynamic_energy, 4),
            "scene_count": scene_count,
            "speech_density": round(speech_density, 4) if speech_density is not None else None,
        },
    }


def _title_from_text(text: str, index: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" -–—,.;:")
    if not cleaned:
        return f"Güçlü an #{index}"
    sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0]
    words = sentence.split()
    title = " ".join(words[:10])
    if len(words) > 10:
        title += "…"
    if title:
        title = title[0].upper() + title[1:]
    return title[:100]


def rank_highlight_candidates(
    duration: float,
    transcript: list[dict[str, Any]],
    energy: list[float],
    energy_step: float,
    scenes: list[float],
    settings: ProjectSettings,
) -> list[dict[str, Any]]:
    candidates = _generate_candidates(duration, transcript, energy, energy_step, scenes, settings)
    scored = [
        _score_candidate(candidate, energy, energy_step, scenes, settings)
        for candidate in candidates
    ]
    scored.sort(key=lambda item: (item["score"], item["confidence"]), reverse=True)
    return scored


def select_diverse_highlights(
    candidates: list[dict[str, Any]],
    *,
    min_score: int,
    clip_count: int,
    decorate: bool = True,
) -> list[dict[str, Any]]:
    eligible = sorted(
        (item for item in candidates if float(item.get("score", 0)) >= min_score),
        key=lambda item: (float(item.get("score", 0)), float(item.get("confidence", 0))),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    for candidate in eligible:
        overlaps = [
            _overlap_ratios(
                (float(candidate["start"]), float(candidate["end"])),
                (float(item["start"]), float(item["end"])),
            )
            for item in selected
        ]
        if all(
            iou <= MAX_DIVERSITY_IOU and containment <= MAX_DIVERSITY_CONTAINMENT
            for iou, containment in overlaps
        ):
            selected.append(candidate)
        if len(selected) >= clip_count:
            break
    if decorate:
        for rank, item in enumerate(selected, start=1):
            item["rank"] = rank
            if not (item.get("semantic_engine") and item.get("title")):
                item["title"] = _title_from_text(str(item.get("text", "")), rank)
    return selected


def select_highlights(
    duration: float,
    transcript: list[dict[str, Any]],
    energy: list[float],
    energy_step: float,
    scenes: list[float],
    settings: ProjectSettings,
) -> list[dict[str, Any]]:
    ranked = rank_highlight_candidates(
        duration,
        transcript,
        energy,
        energy_step,
        scenes,
        settings,
    )
    return select_diverse_highlights(
        ranked,
        min_score=settings.min_score,
        clip_count=settings.clip_count,
    )
