from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


AspectRatio = Literal["9:16", "1:1", "16:9"]
CaptionPreset = Literal["impact", "clean", "boxed", "minimal"]


class ProjectSettings(BaseModel):
    goal: Literal["viral", "education", "podcast", "gaming", "custom"] = "viral"
    aspect_ratio: AspectRatio = "9:16"
    min_duration: float = Field(default=20, ge=5, le=300)
    max_duration: float = Field(default=60, ge=5, le=300)
    clip_count: int = Field(default=5, ge=1, le=12)
    language: str = Field(default="auto", max_length=24)
    caption_preset: CaptionPreset = "impact"
    enable_captions: bool = True
    auto_reframe: bool = True
    remove_silence: bool = False
    prompt: str = Field(default="", max_length=500)
    min_score: int = Field(default=0, ge=0, le=100)
    scene_sensitivity: float = Field(default=0.30, ge=0.10, le=0.80)

    @model_validator(mode="after")
    def validate_duration_range(self) -> "ProjectSettings":
        if self.max_duration < self.min_duration:
            self.max_duration = self.min_duration
        return self


class ClipUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    favorite: bool | None = None
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    aspect_ratio: AspectRatio | None = None
    caption_preset: CaptionPreset | None = None
    enable_captions: bool | None = None
    caption_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    highlight_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_size: int | None = Field(default=None, ge=28, le=110)
    caption_position: Literal["top", "middle", "bottom"] | None = None
    focus_x: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_times(self) -> "ClipUpdate":
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("Bitiş zamanı başlangıçtan büyük olmalı")
        return self
