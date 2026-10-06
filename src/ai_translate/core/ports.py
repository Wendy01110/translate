from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from ai_translate.core.history import HistoryState
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
        """Extract one image within core input limits; never read translation settings."""

    def recognize_pages(
        self,
        pages: Sequence[tuple[bytes, str]],
    ) -> OcrResult:
        """Extract ordered pages within core input limits; never read translation settings."""


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


class LiveResultPresenter(ResultPresenter, Protocol):
    def show_if_current(self, job: TranslateJob, *, is_current: Callable[[], bool]) -> None:
        """Recheck validity on the UI thread before displaying or raising the window."""

    def show_status_if_current(self, message: str, *, is_current: Callable[[], bool]) -> None:
        """Display a live status only while its session and language remain current."""


class HistoryStorage(Protocol):
    def load(self) -> HistoryState:
        """Read bounded local history or report a storage error."""

    def save(self, state: HistoryState) -> HistoryState:
        """Atomically save history within byte limits and return retained entries."""
