from __future__ import annotations

from itertools import combinations

import pytest

from app.schemas import ProjectSettings
from app.scoring import (
    MAX_DIVERSITY_CONTAINMENT,
    MAX_DIVERSITY_IOU,
    Candidate,
    _generate_candidates,
    _score_candidate,
    _tokens,
    select_highlights,
)


def _transcript() -> list[dict[str, object]]:
    texts = [
        "Nasıl gerçek bir sonuç alınır?",
        "Çünkü bu önemli yöntem işe yarıyor.",
        "Sakin ara cümle burada biter.",
        "İşte ikinci şaşırtıcı örnek!",
    ]
    return [
        {
            "start": index * 2.0,
            "end": index * 2.0 + 1.6,
            "text": texts[index % len(texts)],
            "words": [],
        }
        for index in range(20)
    ]


def _settings(*, clip_count: int = 3) -> ProjectSettings:
    return ProjectSettings(
        goal="education",
        min_duration=5,
        max_duration=8,
        clip_count=clip_count,
        min_score=0,
        prompt="önemli yöntem",
    )


def _signals() -> tuple[list[float], list[float]]:
    energy = [0.25, 0.30, 0.80, 0.90, 0.70, 0.20, 0.15, 0.85] * 10
    scenes = [3.0, 11.0, 20.0, 30.0]
    return energy, scenes


def test_generated_candidate_durations_stay_inside_requested_bounds() -> None:
    energy, scenes = _signals()
    candidates = _generate_candidates(
        duration=40,
        transcript=_transcript(),
        energy=energy,
        energy_step=0.5,
        scenes=scenes,
        settings=_settings(),
    )

    assert candidates
    assert all(0 <= item.start < item.end <= 40 for item in candidates)
    assert all(5 <= item.end - item.start <= 8 for item in candidates)


def test_selected_highlights_are_non_overlapping_and_ranked_by_score() -> None:
    energy, scenes = _signals()
    selected = select_highlights(
        duration=40,
        transcript=_transcript(),
        energy=energy,
        energy_step=0.5,
        scenes=scenes,
        settings=_settings(),
    )

    assert len(selected) == 3
    assert [item["rank"] for item in selected] == [1, 2, 3]
    assert [item["score"] for item in selected] == sorted(
        (item["score"] for item in selected),
        reverse=True,
    )
    for left, right in combinations(selected, 2):
        intersection = max(
            0.0,
            min(float(left["end"]), float(right["end"]))
            - max(float(left["start"]), float(right["start"])),
        )
        assert intersection == pytest.approx(0.0)


def test_highlight_selection_is_deterministic() -> None:
    energy, scenes = _signals()
    arguments = {
        "duration": 40,
        "transcript": _transcript(),
        "energy": energy,
        "energy_step": 0.5,
        "scenes": scenes,
        "settings": _settings(),
    }

    first = select_highlights(**arguments)
    second = select_highlights(**arguments)

    assert first == second


def test_short_source_becomes_one_bounded_candidate() -> None:
    candidate = _generate_candidates(
        duration=6.25,
        transcript=[],
        energy=[],
        energy_step=0.5,
        scenes=[],
        settings=_settings(clip_count=1),
    )

    assert len(candidate) == 1
    assert candidate[0].start == 0
    assert candidate[0].end == pytest.approx(6.25)


def test_minimum_score_is_a_strict_output_filter() -> None:
    energy, scenes = _signals()
    settings = _settings()
    settings.min_score = 100

    selected = select_highlights(
        duration=40,
        transcript=_transcript(),
        energy=energy,
        energy_step=0.5,
        scenes=scenes,
        settings=settings,
    )

    assert selected == []


def test_tail_candidates_respect_minimum_duration_and_transcript_bounds() -> None:
    transcript = [
        {
            "start": index * 2.0,
            "end": index * 2.0 + 1.7,
            "text": "Nasıl önemli bir yöntem bulunur?",
            "words": [],
        }
        for index in range(15)
    ]
    settings = ProjectSettings(
        min_duration=18,
        max_duration=22,
        clip_count=5,
        min_score=0,
    )

    candidates = _generate_candidates(
        duration=30,
        transcript=transcript,
        energy=[0.5] * 60,
        energy_step=0.5,
        scenes=[],
        settings=settings,
    )

    assert candidates
    assert all(item.end - item.start >= 18 - 0.01 for item in candidates)
    assert all(
        float(segment["start"]) >= item.start - 0.01
        and float(segment["end"]) <= item.end + 0.01
        for item in candidates
        for segment in item.transcript
    )


def test_diversity_never_fills_quota_with_overlapping_tail_duplicates() -> None:
    transcript = [
        {
            "start": index * 2.0,
            "end": index * 2.0 + 1.7,
            "text": "Nasıl önemli bir yöntem bulunur? Çünkü bu yöntem işe yarar.",
            "words": [],
        }
        for index in range(15)
    ]
    settings = ProjectSettings(
        min_duration=18,
        max_duration=22,
        clip_count=5,
        min_score=0,
    )

    selected = select_highlights(
        duration=30,
        transcript=transcript,
        energy=[0.5] * 60,
        energy_step=0.5,
        scenes=[],
        settings=settings,
    )

    assert 0 < len(selected) < settings.clip_count
    for left, right in combinations(selected, 2):
        intersection = max(
            0.0,
            min(float(left["end"]), float(right["end"]))
            - max(float(left["start"]), float(right["start"])),
        )
        union = max(float(left["end"]), float(right["end"])) - min(
            float(left["start"]), float(right["start"])
        )
        shorter = min(float(left["duration"]), float(right["duration"]))
        assert intersection / union <= MAX_DIVERSITY_IOU
        assert intersection / shorter <= MAX_DIVERSITY_CONTAINMENT


def test_turkish_capital_i_is_one_token_and_late_hook_does_not_boost_opening() -> None:
    assert _tokens("İşte gerçek sonuç") == ["işte", "gerçek", "sonuç"]
    settings = ProjectSettings(goal="custom", min_duration=5, max_duration=20)
    opening = {
        "start": 0.0,
        "end": 4.0,
        "text": "Bugün sakin bir konuyu ayrıntılı olarak ele alıyoruz.",
        "words": [],
    }
    late_hook = {
        "start": 10.0,
        "end": 14.0,
        "text": "İşte gerçek sır burada açıklanıyor.",
        "words": [],
    }
    neutral_end = {
        "start": 10.0,
        "end": 14.0,
        "text": "Bütün ayrıntılar burada açıklanıyor.",
        "words": [],
    }
    late = Candidate(0.0, 20.0, f"{opening['text']} {late_hook['text']}", [opening, late_hook])
    neutral = Candidate(0.0, 20.0, f"{opening['text']} {neutral_end['text']}", [opening, neutral_end])

    late_score = _score_candidate(late, [], 0.5, [], settings)
    neutral_score = _score_candidate(neutral, [], 0.5, [], settings)

    assert late_score["breakdown"]["hook"] == neutral_score["breakdown"]["hook"]
