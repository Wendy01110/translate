from __future__ import annotations

from collections.abc import Sequence

from ai_translate.core.models import (
    JobKind,
    JobStatus,
    TranslateJob,
    TranslationRequest,
)
from ai_translate.core.ports import OcrEngine, Translator


class OcrTranslateService:
    def __init__(self, ocr: OcrEngine, translator: Translator) -> None:
        self._ocr = ocr
        self._translator = translator

    def translate_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslateJob:
        return self.translate_pages(
            [(image_bytes, mime_type)],
            source_lang,
            target_lang,
        )

    def translate_pages(
        self,
        pages: Sequence[tuple[bytes, str]],
        source_lang: str,
        target_lang: str,
    ) -> TranslateJob:
        if not pages or any(not image_bytes for image_bytes, _mime in pages):
            return TranslateJob(
                kind=JobKind.OCR,
                status=JobStatus.FAILURE,
                source_text=None,
                translated_text=None,
                error="empty_image",
            )

        ocr_result = self._ocr.recognize_pages(pages)
        ocr_text = (ocr_result.text or "").strip()
        if ocr_result.status is JobStatus.FAILURE or not ocr_text:
            return TranslateJob(
                kind=JobKind.OCR,
                status=JobStatus.FAILURE,
                source_text=None,
                translated_text=None,
                ocr_text=ocr_result.text,
                error=ocr_result.error or "empty_ocr_text",
                ocr_model=ocr_result.model,
                ocr_engine=ocr_result.engine,
            )

        translation = self._translator.translate(
            TranslationRequest(
                text=ocr_text,
                source_lang=source_lang,
                target_lang=target_lang,
            )
        )
        if translation.status is JobStatus.SUCCESS and translation.translated_text:
            status = JobStatus.SUCCESS
        else:
            status = JobStatus.PARTIAL

        return TranslateJob(
            kind=JobKind.OCR,
            status=status,
            source_text=ocr_text,
            translated_text=translation.translated_text,
            ocr_text=ocr_text,
            error=None if status is JobStatus.SUCCESS else (translation.error or "translate_failed"),
            translate_model=translation.model,
            ocr_model=ocr_result.model,
            ocr_engine=ocr_result.engine,
        )
