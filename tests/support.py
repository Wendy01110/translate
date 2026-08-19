from __future__ import annotations

from collections.abc import Sequence

from ai_translate.core.models import (
    JobStatus,
    OcrResult,
    TranslationRequest,
    TranslationResult,
)


class FakeTranslator:
    def __init__(
        self,
        translated_text: str | None = "你好",
        status: JobStatus = JobStatus.SUCCESS,
        error: str | None = None,
        model: str = "fake-translate",
    ) -> None:
        self.calls: list[TranslationRequest] = []
        self._translated_text = translated_text
        self._status = status
        self._error = error
        self._model = model

    def translate(self, request: TranslationRequest) -> TranslationResult:
        self.calls.append(request)
        return TranslationResult(
            status=self._status,
            source_text=request.text,
            translated_text=self._translated_text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            model=self._model,
            error=self._error,
        )


class FakeOcrEngine:
    def __init__(
        self,
        text: str | None = "Hello",
        status: JobStatus = JobStatus.SUCCESS,
        error: str | None = None,
        model: str = "fake-ocr",
    ) -> None:
        self.calls: list[list[tuple[bytes, str]]] = []
        self._text = text
        self._status = status
        self._error = error
        self._model = model

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        self.calls.append(list(pages))
        return OcrResult(
            status=self._status,
            text=self._text,
            model=self._model,
            error=self._error,
        )
