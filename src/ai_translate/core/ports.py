from __future__ import annotations

from typing import Protocol

from ai_translate.core.models import OcrResult, TranslationRequest, TranslationResult


class Translator(Protocol):
    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate source text. Must not read OCR settings."""


class OcrEngine(Protocol):
    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        """Extract text from an image. Must not read translation settings."""


class TextSource(Protocol):
    def read_selected_text(self) -> str:
        """Return the current selection or an explicit text source."""


class ImageSource(Protocol):
    def capture_region(self) -> bytes:
        """Return image bytes for a captured region."""
