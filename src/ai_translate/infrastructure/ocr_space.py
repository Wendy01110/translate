from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

import httpx

from ai_translate.config import StandardOcrSettings
from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.infrastructure.ocr_text import clean_ocr_text

OCR_SPACE_MAX_IMAGE_BYTES = 1_000_000
OCR_SPACE_MAX_RESPONSE_BYTES = 2_000_000
_SUPPORTED_MIME_TYPES = frozenset(
    {
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }
)


class OcrSpaceEngine:
    def __init__(
        self,
        settings: StandardOcrSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
        )

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        if not self._settings.ready:
            return self._failure("ocr_standard_not_configured")
        if not pages or any(not image_bytes for image_bytes, _mime_type in pages):
            return self._failure("empty_image")
        if len(pages) != 1:
            return self._failure("ocr_standard_multi_page_unsupported")
        image_bytes, mime_type = pages[0]
        if len(image_bytes) > OCR_SPACE_MAX_IMAGE_BYTES:
            return self._failure("ocr_standard_image_too_large")
        if mime_type.lower() not in _SUPPORTED_MIME_TYPES:
            return self._failure("ocr_standard_image_type_unsupported")

        data_uri = (
            f"data:{mime_type};base64," + base64.b64encode(image_bytes).decode("ascii")
        )
        files = {
            "base64Image": (None, data_uri),
            "language": (None, self._settings.language),
            "isOverlayRequired": (None, "false"),
            "detectOrientation": (None, "true"),
            "OCREngine": (None, str(self._settings.engine)),
        }
        try:
            response = self._client.post(
                self._settings.base_url,
                headers={"apikey": self._settings.api_key.get_secret_value()},
                files=files,
                timeout=self._settings.timeout_seconds,
            )
        except httpx.TimeoutException:
            return self._failure("timeout")
        except httpx.HTTPError:
            return self._failure("http_error")

        if len(response.content) > OCR_SPACE_MAX_RESPONSE_BYTES:
            return self._failure("ocr_response_too_large")
        try:
            body = response.json()
        except ValueError:
            return self._failure("invalid_json")
        if response.status_code >= 400:
            return self._failure(f"http_{response.status_code}")
        if not isinstance(body, dict):
            return self._failure("invalid_json")
        raw_text = _parsed_text(body)
        if raw_text is None:
            return self._failure("empty_ocr_text")
        cleaned = clean_ocr_text(raw_text)
        if not cleaned:
            return self._failure("empty_ocr_text")
        return OcrResult(
            status=JobStatus.SUCCESS,
            text=cleaned,
            model=self._model_name,
            raw_text=raw_text,
            engine="standard",
        )

    @property
    def _model_name(self) -> str:
        return f"ocr.space-engine-{self._settings.engine}"

    def _failure(self, error: str) -> OcrResult:
        return OcrResult(
            status=JobStatus.FAILURE,
            text=None,
            model=self._model_name,
            error=error,
            engine="standard",
        )


def _parsed_text(payload: dict[str, Any]) -> str | None:
    if payload.get("IsErroredOnProcessing") is True:
        return None
    if payload.get("OCRExitCode") not in {1, 2, "1", "2"}:
        return None
    parsed_results = payload.get("ParsedResults")
    if not isinstance(parsed_results, list) or not parsed_results:
        return None
    parts: list[str] = []
    for item in parsed_results:
        if not isinstance(item, dict):
            continue
        if item.get("FileParseExitCode") not in {None, 1, "1"}:
            continue
        value = item.get("ParsedText")
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    if not parts:
        return None
    return "\n".join(parts)
