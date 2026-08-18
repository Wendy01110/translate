from __future__ import annotations

import base64

import httpx

from ai_translate.config import OcrSettings
from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.infrastructure.openai_compat import message_text, post_chat_completion

_OCR_PROMPT = (
    "Extract all visible text from the image. "
    "Preserve original line breaks. Return only the extracted text."
)


class HttpOcrEngine:
    def __init__(self, settings: OcrSettings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client()

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        if not self._settings.ready:
            return OcrResult(
                status=JobStatus.FAILURE,
                text=None,
                model=self._settings.model,
                error="ocr_not_configured",
            )
        if not image_bytes:
            return OcrResult(
                status=JobStatus.FAILURE,
                text=None,
                model=self._settings.model,
                error="empty_image",
            )

        encoded = base64.b64encode(image_bytes).decode("ascii")
        image_url = f"data:{mime_type};base64,{encoded}"
        _, body, error = post_chat_completion(
            self._client,
            base_url=self._settings.base_url,
            api_key=self._settings.api_key.get_secret_value(),
            timeout_seconds=self._settings.timeout_seconds,
            payload={
                "model": self._settings.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _OCR_PROMPT},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                "store": False,
            },
        )
        if error or body is None:
            return OcrResult(
                status=JobStatus.FAILURE,
                text=None,
                model=self._settings.model,
                error=error or "empty_response",
            )

        text = message_text(body)
        if text is None:
            return OcrResult(
                status=JobStatus.FAILURE,
                text=None,
                model=self._settings.model,
                error="empty_ocr_text",
            )
        return OcrResult(
            status=JobStatus.SUCCESS,
            text=text,
            model=self._settings.model,
        )
