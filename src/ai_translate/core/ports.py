from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ai_translate.core.models import (
    OcrResult,
    TranslateJob,
    TranslationRequest,
    TranslationResult,
)


class Translator(Protocol):
    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate source text. Must not read OCR settings."""


class OcrEngine(Protocol):
    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        """Extract text from one image. Must not read translation settings."""

    def recognize_pages(
        self,
        pages: Sequence[tuple[bytes, str]],
    ) -> OcrResult:
        """Extract text from one or more images. Must not read translation settings."""


class TextSource(Protocol):
    def read_selected_text(self) -> str:
        """Return the current selection or an explicit text source."""


class ImageSource(Protocol):
    def capture_region(self) -> tuple[bytes, str]:
        """Return image bytes and mime type for a captured region."""


class ResultPresenter(Protocol):
    def show_status(self, message: str, source: str | None = None) -> None:
        """Show an in-progress message. CLI may ignore this."""

    def show(self, job: TranslateJob) -> None:
        """Show a finished translation job."""
