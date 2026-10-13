from __future__ import annotations

from pathlib import Path

from app.captions import create_ass_subtitles, create_srt_subtitles


def test_ass_subtitles_are_clip_relative_styled_and_escaped(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "captions.ass"
    transcript = [
        {
            "start": 9.8,
            "end": 13.0,
            "text": "Merhaba {dünya}! İkinci satır.",
            "words": [
                {"start": 9.9, "end": 10.2, "text": "Merhaba"},
                {"start": 10.25, "end": 10.8, "text": "{dünya}!"},
                {"start": 12.0, "end": 12.3, "text": "İkinci"},
                {"start": 12.32, "end": 12.8, "text": "satır."},
            ],
        }
    ]

    created = create_ass_subtitles(
        output,
        transcript,
        clip_start=10.0,
        clip_end=15.0,
        preset_name="boxed",
        resolution=(1080, 1920),
        primary_color="#112233",
        highlight_color="#AABBCC",
        position="top",
    )

    assert created is True
    content = output.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "&H00332211" in content
    assert "&H00CCBBAA" in content
    assert "Dialogue: 0,0:00:00.00," in content
    assert r"\{dünya\}!" in content
    assert content.count("Dialogue: ") == 2


def test_ass_returns_false_when_no_word_timestamps_overlap(tmp_path: Path) -> None:
    output = tmp_path / "captions.ass"

    created = create_ass_subtitles(
        output,
        [{"start": 0, "end": 1, "text": "Metin var ama kelime zamanı yok."}],
        clip_start=0,
        clip_end=1,
    )

    assert created is False
    assert not output.exists()


def test_srt_subtitles_clip_boundary_times_and_excludes_outside_segments(
    tmp_path: Path,
) -> None:
    output = tmp_path / "captions.srt"
    transcript = [
        {"start": 8.0, "end": 9.0, "text": "Dışarıda"},
        {"start": 9.5, "end": 11.0, "text": "Başlangıca taşan bölüm"},
        {"start": 13.25, "end": 15.8, "text": "Bitişe taşan bölüm"},
        {"start": 15.0, "end": 16.0, "text": "Bu da dışarıda"},
    ]

    created = create_srt_subtitles(output, transcript, clip_start=10.0, clip_end=15.0)

    assert created is True
    assert output.read_text(encoding="utf-8") == (
        "1\n"
        "00:00:00,000 --> 00:00:01,000\n"
        "Başlangıca taşan bölüm\n\n"
        "2\n"
        "00:00:03,250 --> 00:00:05,000\n"
        "Bitişe taşan bölüm\n"
    )


def test_srt_returns_false_without_an_overlapping_segment(tmp_path: Path) -> None:
    output = tmp_path / "captions.srt"

    created = create_srt_subtitles(
        output,
        [{"start": 0, "end": 1, "text": "Dışarıda"}],
        clip_start=2,
        clip_end=3,
    )

    assert created is False
    assert not output.exists()
