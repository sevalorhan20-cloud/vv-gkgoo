from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PRESETS = {
    "impact": {
        "font": "DejaVu Sans",
        "size": 72,
        "primary": "&H00FFFFFF",
        "secondary": "&H0055E6A6",
        "outline": "&H00100B08",
        "back": "&H90000000",
        "border": 1,
        "outline_width": 5,
        "shadow": 1,
        "bold": -1,
    },
    "clean": {
        "font": "DejaVu Sans",
        "size": 62,
        "primary": "&H00FFFFFF",
        "secondary": "&H0055E6A6",
        "outline": "&H00100B08",
        "back": "&H40000000",
        "border": 1,
        "outline_width": 3,
        "shadow": 1,
        "bold": -1,
    },
    "boxed": {
        "font": "DejaVu Sans",
        "size": 60,
        "primary": "&H00080B10",
        "secondary": "&H00080B10",
        "outline": "&H0055E6A6",
        "back": "&H0055E6A6",
        "border": 3,
        "outline_width": 12,
        "shadow": 0,
        "bold": -1,
    },
    "minimal": {
        "font": "DejaVu Sans",
        "size": 54,
        "primary": "&H00FFFFFF",
        "secondary": "&H0055E6A6",
        "outline": "&H00100B08",
        "back": "&H00000000",
        "border": 1,
        "outline_width": 2,
        "shadow": 0,
        "bold": 0,
    },
}


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds % 60
    return f"{hours}:{minutes:02d}:{remainder:05.2f}"


def _ass_color(hex_color: str, alpha: str = "00") -> str:
    raw = hex_color.lstrip("#")
    if len(raw) != 6:
        return "&H00FFFFFF"
    red, green, blue = raw[:2], raw[2:4], raw[4:6]
    return f"&H{alpha}{blue}{green}{red}".upper()


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _word_groups(words: list[dict[str, Any]], maximum_words: int = 5) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        if current and (float(word["start"]) - float(current[-1]["end"]) > 0.45 or len(current) >= maximum_words):
            groups.append(current)
            current = []
        current.append(word)
        if re.search(r"[.!?…]$", str(word.get("text", ""))) or len(current) >= maximum_words:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def create_ass_subtitles(
    output: Path,
    transcript: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    *,
    preset_name: str = "impact",
    resolution: tuple[int, int] = (1080, 1920),
    primary_color: str = "#FFFFFF",
    highlight_color: str = "#65E6B4",
    font_size: int | None = None,
    position: str = "bottom",
) -> bool:
    words: list[dict[str, Any]] = []
    for segment in transcript:
        for word in segment.get("words") or []:
            if float(word.get("end", 0)) > clip_start and float(word.get("start", 0)) < clip_end:
                words.append(word)
    if not words:
        return False
    preset = dict(PRESETS.get(preset_name, PRESETS["impact"]))
    preset["primary"] = _ass_color(primary_color)
    preset["secondary"] = _ass_color(highlight_color)
    if font_size:
        preset["size"] = font_size
    width, height = resolution
    scale = height / 1920
    margin_v = int(({"top": 140, "middle": 0, "bottom": 250}.get(position, 250)) * scale)
    alignment = {"top": 8, "middle": 5, "bottom": 2}.get(position, 2)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{preset['font']},{int(preset['size'] * scale)},{preset['primary']},{preset['secondary']},{preset['outline']},{preset['back']},{preset['bold']},0,0,0,100,100,0,0,{preset['border']},{preset['outline_width']},{preset['shadow']},{alignment},70,70,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for group in _word_groups(words):
        start = max(0.0, float(group[0]["start"]) - clip_start)
        end = min(clip_end - clip_start, float(group[-1]["end"]) - clip_start + 0.08)
        karaoke: list[str] = []
        for word in group:
            duration_cs = max(1, int(round((float(word["end"]) - float(word["start"])) * 100)))
            karaoke.append(r"{\kf" + str(duration_cs) + "}" + _escape(str(word.get("text", "")).strip()))
        text = " ".join(karaoke)
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Main,,0,0,0,,{text}\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8")
    return True


def create_srt_subtitles(
    output: Path,
    transcript: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> bool:
    selected = [
        item for item in transcript
        if float(item.get("end", 0)) > clip_start and float(item.get("start", 0)) < clip_end
    ]
    if not selected:
        return False

    def stamp(seconds: float) -> str:
        milliseconds = int(round(max(0, seconds) * 1000))
        hours, milliseconds = divmod(milliseconds, 3_600_000)
        minutes, milliseconds = divmod(milliseconds, 60_000)
        whole_seconds, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"

    blocks = []
    for index, item in enumerate(selected, start=1):
        start = max(0, float(item["start"]) - clip_start)
        end = min(clip_end - clip_start, float(item["end"]) - clip_start)
        blocks.append(f"{index}\n{stamp(start)} --> {stamp(end)}\n{item.get('text', '').strip()}\n")
    output.write_text("\n".join(blocks), encoding="utf-8")
    return True
