from __future__ import annotations

import sys
from collections.abc import Callable, Sequence

from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.core.ocr_input import ocr_pages_error

VisionRecognize = Callable[[bytes, str], tuple[str, float | None]]

_VISION_AVAILABLE: bool | None = None


def vision_available() -> bool:
    global _VISION_AVAILABLE
    if _VISION_AVAILABLE is not None:
        return _VISION_AVAILABLE
    if sys.platform != "darwin":
        _VISION_AVAILABLE = False
        return False
    try:
        import Vision  # noqa: F401
        from Quartz import CGImageSourceCreateWithData  # noqa: F401
    except Exception:
        _VISION_AVAILABLE = False
        return False
    _VISION_AVAILABLE = True
    return True


class VisionOcrEngine:
    def __init__(
        self,
        *,
        recognize: VisionRecognize | None = None,
    ) -> None:
        self._recognize = recognize or _recognize_with_vision

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        error = ocr_pages_error(pages)
        if error:
            return _failure(error)
        texts: list[str] = []
        scores: list[float] = []
        try:
            for image_bytes, mime_type in pages:
                text, confidence = self._recognize(image_bytes, mime_type)
                cleaned = text.strip()
                if cleaned:
                    texts.append(cleaned)
                if confidence is not None:
                    scores.append(confidence)
        except Exception:
            return _failure("vision_failed")
        joined = "\n".join(texts).strip()
        if not joined:
            return _failure("empty_ocr_text")
        average = sum(scores) / len(scores) if scores else None
        return OcrResult(
            status=JobStatus.SUCCESS,
            text=joined,
            model="macos-vision",
            engine="vision",
            confidence=average,
        )


def _failure(error: str) -> OcrResult:
    return OcrResult(
        status=JobStatus.FAILURE,
        text=None,
        model="macos-vision",
        error=error,
        engine="vision",
    )


def _recognize_with_vision(image_bytes: bytes, _mime_type: str) -> tuple[str, float | None]:
    from Foundation import NSData
    from Quartz import CGImageSourceCreateImageAtIndex, CGImageSourceCreateWithData
    from Vision import VNImageRequestHandler, VNRecognizeTextRequest

    data = NSData.dataWithBytes_length_(image_bytes, len(image_bytes))
    source = CGImageSourceCreateWithData(data, None)
    image = CGImageSourceCreateImageAtIndex(source, 0, None)
    if image is None:
        return "", None
    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(0)
    request.setUsesLanguageCorrection_(True)
    try:
        request.setRecognitionLanguages_(["en-US", "zh-Hans", "zh-Hant", "ja-JP"])
    except Exception:
        pass
    handler = VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, _error = handler.performRequests_error_([request], None)
    if not ok:
        return "", None
    lines: list[str] = []
    scores: list[float] = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        candidate = candidates[0]
        text = str(candidate.string() or "").strip()
        if text:
            lines.append(text)
            scores.append(float(candidate.confidence()))
    confidence = sum(scores) / len(scores) if scores else None
    return "\n".join(lines), confidence
