from __future__ import annotations

import importlib.util
from collections.abc import Callable, Mapping, Sequence
from io import BytesIO
from threading import Lock
from typing import Any

from ai_translate.config import LocalAdvancedOcrSettings
from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.infrastructure.ocr_text import clean_ocr_text

MAX_LOCAL_OCR_PIXELS = 40_000_000

PaddleFactory = Callable[..., Any]
ImageDecoder = Callable[[bytes], Any]
FirstLoadNotifier = Callable[[str], None]


def paddle_ocr_available() -> bool:
    try:
        return (
            importlib.util.find_spec("paddleocr") is not None
            and importlib.util.find_spec("paddle") is not None
        )
    except (ImportError, ValueError):
        return False


class PaddleOcrEngine:
    def __init__(
        self,
        settings: LocalAdvancedOcrSettings,
        *,
        factory: PaddleFactory | None = None,
        decoder: ImageDecoder | None = None,
        on_first_load: FirstLoadNotifier | None = None,
    ) -> None:
        self._settings = settings
        self._factory = factory or _default_factory
        self._decoder = decoder or _decode_image
        self._on_first_load = on_first_load
        self._first_load_notified = False
        self._pipeline: Any | None = None
        self._lock = Lock()

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        if not pages or any(not image_bytes for image_bytes, _mime in pages):
            return self._failure("empty_image")

        with self._lock:
            try:
                pipeline = self._get_pipeline()
            except ModuleNotFoundError:
                return self._failure("paddle_ocr_not_installed")
            except Exception:
                return self._failure("paddle_ocr_init_failed")

            page_texts: list[str] = []
            scores: list[float] = []
            try:
                for image_bytes, _mime_type in pages:
                    image = self._decoder(image_bytes)
                    text, page_scores = _extract_prediction(pipeline.predict(image))
                    if text:
                        page_texts.append(text)
                    scores.extend(page_scores)
            except _InvalidImage:
                return self._failure("invalid_image")
            except Exception:
                return self._failure("paddle_ocr_failed")

        text = clean_ocr_text("\n".join(page_texts))
        if not text:
            return self._failure("empty_ocr_text")
        confidence = sum(scores) / len(scores) if scores else None
        return OcrResult(
            status=JobStatus.SUCCESS,
            text=text,
            model=self._settings.model,
            engine="paddle",
            confidence=confidence,
        )

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            self._notify_first_load()
            tier = self._settings.model_tier
            self._pipeline = self._factory(
                text_detection_model_name=f"PP-OCRv6_{tier}_det",
                text_recognition_model_name=f"PP-OCRv6_{tier}_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                device=self._settings.device,
            )
        return self._pipeline

    def _notify_first_load(self) -> None:
        if self._first_load_notified:
            return
        self._first_load_notified = True
        if self._on_first_load is None:
            return
        try:
            self._on_first_load(self._settings.model)
        except Exception:
            pass

    def _failure(self, error: str) -> OcrResult:
        return OcrResult(
            status=JobStatus.FAILURE,
            text=None,
            model=self._settings.model,
            error=error,
            engine="paddle",
        )


class _InvalidImage(Exception):
    pass


def _default_factory(**kwargs: Any) -> Any:
    from paddleocr import PaddleOCR

    return PaddleOCR(**kwargs)


def _decode_image(image_bytes: bytes) -> Any:
    try:
        import numpy as np
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_LOCAL_OCR_PIXELS:
                raise _InvalidImage
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    except _InvalidImage:
        raise
    except Exception as exc:
        raise _InvalidImage from exc
    return rgb[:, :, ::-1].copy()


def _extract_prediction(results: Any) -> tuple[str, list[float]]:
    texts: list[str] = []
    scores: list[float] = []
    if results is None:
        return "", scores
    for result in results:
        payload = _prediction_payload(result)
        raw_texts = _as_list(payload.get("rec_texts"))
        raw_scores = _as_list(payload.get("rec_scores"))
        for index, raw_text in enumerate(raw_texts):
            text = str(raw_text).strip()
            if not text:
                continue
            texts.append(text)
            if index < len(raw_scores):
                try:
                    scores.append(float(raw_scores[index]))
                except (TypeError, ValueError):
                    pass
    return "\n".join(texts), scores


def _prediction_payload(result: Any) -> Mapping[str, Any]:
    payload: Any = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if not isinstance(payload, Mapping) and isinstance(result, Mapping):
        payload = result
    if not isinstance(payload, Mapping):
        return {}
    nested = payload.get("res")
    return nested if isinstance(nested, Mapping) else payload


def _as_list(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes, bytearray)):
        return []
    try:
        return list(value)
    except TypeError:
        return []
