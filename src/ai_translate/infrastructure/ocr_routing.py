from __future__ import annotations

from collections.abc import Sequence

from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.core.ocr_input import ocr_pages_error
from ai_translate.core.ports import OcrEngine
from ai_translate.infrastructure.ocr_space import OCR_SPACE_MAX_IMAGE_BYTES


class TieredLocalOcrEngine:
    def __init__(
        self,
        *,
        standard: OcrEngine | None,
        advanced: OcrEngine | None,
        min_confidence: float,
    ) -> None:
        self._standard = standard
        self._advanced = advanced
        self._min_confidence = min_confidence

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        error = ocr_pages_error(pages)
        if error:
            return _failure(error)
        standard_result: OcrResult | None = None
        if self._standard is not None:
            standard_result = self._standard.recognize_pages(pages)
            if _acceptable(standard_result, self._min_confidence):
                return standard_result
        if self._advanced is not None:
            return self._advanced.recognize_pages(pages)
        return standard_result or _failure("local_ocr_unavailable")


class TieredRemoteOcrEngine:
    def __init__(
        self,
        *,
        standard: OcrEngine | None,
        advanced: OcrEngine | None,
        standard_max_image_bytes: int = OCR_SPACE_MAX_IMAGE_BYTES,
    ) -> None:
        self._standard = standard
        self._advanced = advanced
        self._standard_max_image_bytes = standard_max_image_bytes

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        error = ocr_pages_error(pages)
        if error:
            return _failure(error)
        standard_result: OcrResult | None = None
        if self._standard is not None and self._is_standard_candidate(pages):
            standard_result = self._standard.recognize_pages(pages)
            if _successful(standard_result):
                return standard_result
        if self._advanced is not None:
            return self._advanced.recognize_pages(pages)
        return standard_result or _failure("ocr_not_configured")

    def _is_standard_candidate(
        self,
        pages: Sequence[tuple[bytes, str]],
    ) -> bool:
        return (
            len(pages) == 1
            and bool(pages[0][0])
            and len(pages[0][0]) <= self._standard_max_image_bytes
        )


class RoutingOcrEngine:
    def __init__(
        self,
        *,
        local: OcrEngine | None,
        remote: OcrEngine | None,
        mode: str,
        min_confidence: float,
    ) -> None:
        self._local = local
        self._remote = remote
        self._mode = mode
        self._min_confidence = min_confidence

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        error = ocr_pages_error(pages)
        if error:
            return _failure(error)
        if self._mode in {"model", "standard"}:
            return self._require_remote(pages)
        local_result = self._try_local(pages)
        if self._mode in {"vision", "paddle"}:
            return local_result or _failure(f"{self._mode}_unavailable")
        if local_result is not None and _acceptable(local_result, self._min_confidence):
            return local_result
        if self._remote is not None:
            return self._remote.recognize_pages(pages)
        return local_result or _failure("ocr_not_configured")

    def _try_local(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult | None:
        if self._local is None:
            return None
        return self._local.recognize_pages(pages)

    def _require_remote(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        if self._remote is None:
            return _failure("ocr_not_configured")
        return self._remote.recognize_pages(pages)


def _acceptable(result: OcrResult, min_confidence: float) -> bool:
    if not _successful(result):
        return False
    if result.confidence is None:
        return True
    return result.confidence >= min_confidence


def _successful(result: OcrResult) -> bool:
    return result.status is JobStatus.SUCCESS and bool((result.text or "").strip())


def _failure(error: str) -> OcrResult:
    return OcrResult(
        status=JobStatus.FAILURE,
        text=None,
        model="",
        error=error,
        engine=None,
    )
