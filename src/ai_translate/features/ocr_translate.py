from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ai_translate.core.models import (
    JobKind,
    JobStatus,
    TranslateJob,
    TranslationRequest,
)
from ai_translate.core.ports import OcrEngine, Translator

LIVE_SKIP_FRAME = "skip_frame"
LIVE_SKIP_TEXT = "skip_text"
LIVE_SHOW = "show"
LIVE_STOPPED = "stopped"


def image_signature(image_bytes: bytes) -> str:
    return hashlib.blake2s(image_bytes, digest_size=16).hexdigest()


@dataclass(frozen=True)
class LiveOcrMemory:
    frame_hash: str = ""
    ocr_text: str = ""


@dataclass(frozen=True)
class LiveOcrAdvance:
    action: str
    memory: LiveOcrMemory
    job: TranslateJob | None


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
            error=(
                None
                if status is JobStatus.SUCCESS
                else (translation.error or "translate_failed")
            ),
            translate_model=translation.model,
            ocr_model=ocr_result.model,
            ocr_engine=ocr_result.engine,
        )

    def advance_live(
        self,
        image_bytes: bytes,
        mime_type: str,
        source_lang: str,
        target_lang: str,
        *,
        frame_hash: str,
        memory: LiveOcrMemory,
        should_continue: Callable[[], bool] | None = None,
    ) -> LiveOcrAdvance:
        if should_continue is not None and not should_continue():
            return LiveOcrAdvance(LIVE_STOPPED, memory, None)
        if frame_hash and frame_hash == memory.frame_hash:
            return LiveOcrAdvance(LIVE_SKIP_FRAME, memory, None)
        if not image_bytes:
            job = TranslateJob(
                kind=JobKind.OCR,
                status=JobStatus.FAILURE,
                source_text=None,
                translated_text=None,
                error="empty_image",
            )
            return LiveOcrAdvance(
                LIVE_SHOW,
                LiveOcrMemory(frame_hash=frame_hash, ocr_text=""),
                job,
            )

        ocr_result = self._ocr.recognize_pages([(image_bytes, mime_type)])
        if should_continue is not None and not should_continue():
            return LiveOcrAdvance(LIVE_STOPPED, memory, None)
        ocr_text = (ocr_result.text or "").strip()
        next_memory = LiveOcrMemory(frame_hash=frame_hash, ocr_text=ocr_text)
        if ocr_result.status is JobStatus.FAILURE or not ocr_text:
            job = TranslateJob(
                kind=JobKind.OCR,
                status=JobStatus.FAILURE,
                source_text=None,
                translated_text=None,
                ocr_text=ocr_result.text,
                error=ocr_result.error or "empty_ocr_text",
                ocr_model=ocr_result.model,
                ocr_engine=ocr_result.engine,
            )
            return LiveOcrAdvance(LIVE_SHOW, next_memory, job)
        if ocr_text == memory.ocr_text:
            return LiveOcrAdvance(LIVE_SKIP_TEXT, next_memory, None)

        translation = self._translator.translate(
            TranslationRequest(
                text=ocr_text,
                source_lang=source_lang,
                target_lang=target_lang,
            )
        )
        if should_continue is not None and not should_continue():
            return LiveOcrAdvance(LIVE_STOPPED, memory, None)
        if translation.status is JobStatus.SUCCESS and translation.translated_text:
            status = JobStatus.SUCCESS
        else:
            status = JobStatus.PARTIAL
        job = TranslateJob(
            kind=JobKind.OCR,
            status=status,
            source_text=ocr_text,
            translated_text=translation.translated_text,
            ocr_text=ocr_text,
            error=(
                None
                if status is JobStatus.SUCCESS
                else (translation.error or "translate_failed")
            ),
            translate_model=translation.model,
            ocr_model=ocr_result.model,
            ocr_engine=ocr_result.engine,
        )
        return LiveOcrAdvance(LIVE_SHOW, next_memory, job)
