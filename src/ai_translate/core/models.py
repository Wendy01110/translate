from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JobKind(str, Enum):
    SELECTION = "selection"
    OCR = "ocr"


class JobStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


@dataclass(frozen=True)
class ScreenRect:
    x: float
    y: float
    width: float
    height: float

    def canonical(self) -> ScreenRect:
        x, y, width, height = self.x, self.y, self.width, self.height
        if width < 0:
            x += width
            width = -width
        if height < 0:
            y += height
            height = -height
        return ScreenRect(x=x, y=y, width=width, height=height)

    def is_usable(self, min_size: float = 16.0) -> bool:
        rect = self.canonical()
        return rect.width >= min_size and rect.height >= min_size


@dataclass(frozen=True)
class TranslationRequest:
    text: str
    source_lang: str
    target_lang: str


@dataclass(frozen=True)
class TranslationResult:
    status: JobStatus
    source_text: str
    translated_text: str | None
    source_lang: str
    target_lang: str
    model: str
    error: str | None = None


@dataclass(frozen=True)
class OcrResult:
    status: JobStatus
    text: str | None
    model: str
    error: str | None = None
    raw_text: str | None = None
    image_mode: str | None = None
    engine: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ConfigStatus:
    translate_ready: bool
    translate_provider: str
    translate_base_url: str
    translate_model: str
    translate_api_key_set: bool
    translate_source_lang: str
    translate_target_lang: str
    ocr_ready: bool
    ocr_base_url: str
    ocr_model: str
    ocr_api_key_set: bool
    ocr_image_mode: str
    ocr_max_tokens: int
    ocr_engine: str
    ocr_vision_available: bool
    ocr_local_advanced_available: bool
    ocr_local_advanced_model: str
    hotkey_selection: str
    hotkey_ocr: str
    hotkey_live_ocr: str = "alt+q"
    env_file: str = ""
    ocr_standard_ready: bool = False
    ocr_standard_base_url: str = ""
    ocr_standard_api_key_set: bool = False
    ocr_standard_engine: int = 2
    ocr_standard_max_image_bytes: int = 1_000_000
    ocr_advanced_ready: bool = False
    translate_router_thinking: bool | None = None
    ocr_router_thinking: bool | None = None


@dataclass(frozen=True)
class TranslateJob:
    kind: JobKind
    status: JobStatus
    source_text: str | None
    translated_text: str | None
    ocr_text: str | None = None
    error: str | None = None
    translate_model: str | None = None
    ocr_model: str | None = None
    ocr_engine: str | None = None
