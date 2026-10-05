from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from ai_translate.core.limits import MAX_TRANSLATION_CHARS
from ai_translate.core.models import (
    JobKind,
    JobStatus,
    OcrResult,
    TranslateJob,
    TranslationRequest,
    TranslationResult,
)
from ai_translate.core.ocr_input import ocr_pages_error
from ai_translate.core.ports import OcrEngine, Translator

LIVE_SKIP_FRAME = "skip_frame"
LIVE_SKIP_TEXT = "skip_text"
LIVE_SHOW = "show"
LIVE_STOPPED = "stopped"
_LIVE_RETRY_DELAYS_SECONDS = (2.0, 5.0)
_RETRYABLE_TRANSLATION_ERRORS = frozenset(
    {
        "timeout",
        "http_error",
        "http_408",
        "http_429",
        "http_500",
        "http_502",
        "http_503",
        "http_504",
    }
)


def image_signature(image_bytes: bytes) -> str:
    return hashlib.blake2s(image_bytes, digest_size=16).hexdigest()


@dataclass(frozen=True)
class LiveOcrMemory:
    frame_hash: str = ""
    ocr_text: str = ""
    retry_count: int = 0
    retry_at: float | None = None
    retry_ocr: OcrResult | None = None


@dataclass(frozen=True)
class LiveOcrAdvance:
    action: str
    memory: LiveOcrMemory
    job: TranslateJob | None


class OcrTranslateService:
    def __init__(
        self,
        ocr: OcrEngine,
        translator: Translator,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ocr = ocr
        self._translator = translator
        self._clock = clock

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
        error = ocr_pages_error(pages)
        if error:
            return TranslateJob(
                kind=JobKind.OCR,
                status=JobStatus.FAILURE,
                source_text=None,
                translated_text=None,
                error=error,
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

        translation = self._translate_text(ocr_text, source_lang, target_lang)
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
        same_frame = bool(frame_hash) and frame_hash == memory.frame_hash
        retry_due = memory.retry_at is not None and self._clock() >= memory.retry_at
        if same_frame and not retry_due:
            return LiveOcrAdvance(LIVE_SKIP_FRAME, memory, None)
        error = ocr_pages_error([(image_bytes, mime_type)])
        if error:
            job = TranslateJob(
                kind=JobKind.OCR,
                status=JobStatus.FAILURE,
                source_text=None,
                translated_text=None,
                error=error,
            )
            return LiveOcrAdvance(
                LIVE_SHOW,
                LiveOcrMemory(frame_hash=frame_hash, ocr_text=""),
                job,
            )

        ocr_result = (
            memory.retry_ocr
            if same_frame and memory.retry_ocr is not None
            else self._ocr.recognize_pages([(image_bytes, mime_type)])
        )
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
        same_text = ocr_text == memory.ocr_text
        if same_text and not retry_due:
            return LiveOcrAdvance(
                LIVE_SKIP_TEXT,
                replace(
                    memory,
                    frame_hash=frame_hash,
                    retry_ocr=ocr_result if memory.retry_ocr is not None else None,
                ),
                None,
            )

        translation = self._translate_text(ocr_text, source_lang, target_lang)
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
        if status is JobStatus.PARTIAL:
            retry_count = memory.retry_count + 1 if same_text else 0
            retry_at = None
            if (
                job.error in _RETRYABLE_TRANSLATION_ERRORS
                and retry_count < len(_LIVE_RETRY_DELAYS_SECONDS)
            ):
                retry_at = self._clock() + _LIVE_RETRY_DELAYS_SECONDS[retry_count]
            next_memory = LiveOcrMemory(
                frame_hash=frame_hash,
                ocr_text=ocr_text,
                retry_count=retry_count,
                retry_at=retry_at,
                retry_ocr=ocr_result if retry_at is not None else None,
            )
        return LiveOcrAdvance(LIVE_SHOW, next_memory, job)

    def _translate_text(
        self, text: str, source_lang: str, target_lang: str,
    ) -> TranslationResult:
        if len(text) > MAX_TRANSLATION_CHARS:
            return TranslationResult(
                status=JobStatus.FAILURE,
                source_text=text,
                translated_text=None,
                source_lang=source_lang,
                target_lang=target_lang,
                model="",
                error="text_too_long",
            )
        return self._translator.translate(TranslationRequest(text, source_lang, target_lang))
