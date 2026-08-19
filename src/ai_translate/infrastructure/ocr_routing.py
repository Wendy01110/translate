from __future__ import annotations

from collections.abc import Sequence

from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.core.ports import OcrEngine


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
        if self._mode == "model":
            return self._require_remote(pages)
        local_result = self._try_local(pages)
        if self._mode == "vision":
            return local_result or _failure("vision_unavailable")
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


def build_ocr_engine(
    *,
    local: OcrEngine | None,
    remote: OcrEngine | None,
    mode: str,
    min_confidence: float,
) -> RoutingOcrEngine:
    return RoutingOcrEngine(
        local=local,
        remote=remote,
        mode=mode,
        min_confidence=min_confidence,
    )


def _acceptable(result: OcrResult, min_confidence: float) -> bool:
    if result.status is not JobStatus.SUCCESS or not (result.text or "").strip():
        return False
    if result.confidence is None:
        return True
    return result.confidence >= min_confidence


def _failure(error: str) -> OcrResult:
    return OcrResult(
        status=JobStatus.FAILURE,
        text=None,
        model="",
        error=error,
        engine=None,
    )
