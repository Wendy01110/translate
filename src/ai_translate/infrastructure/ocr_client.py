from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

import httpx

from ai_translate.config import OcrSettings
from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.infrastructure.ocr_text import clean_ocr_text
from ai_translate.infrastructure.openai_compat import (
    chat_completions_url,
    post_chat_completion,
)

_SINGLE_PROMPT = "document parsing."
_MULTI_PROMPT = "Multi page parsing."
_MULTI_IMAGE_MODES = frozenset({"tiny", "small", "base"})


class HttpOcrEngine:
    def __init__(
        self,
        settings: OcrSettings,
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
            return self._failure("ocr_not_configured")
        if not pages or any(not image_bytes for image_bytes, _mime in pages):
            return self._failure("empty_image")

        try:
            image_mode = resolve_image_mode(len(pages), self._settings.image_mode)
        except ValueError:
            return self._failure("ocr_image_mode_unsupported")

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": _SINGLE_PROMPT if len(pages) == 1 else _MULTI_PROMPT,
            }
        ]
        content.extend(
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{mime_type};base64,"
                        + base64.b64encode(image_bytes).decode("ascii")
                    )
                },
            }
            for image_bytes, mime_type in pages
        )
        _, body, error = post_chat_completion(
            self._client,
            base_url=self._settings.base_url,
            api_key=self._settings.api_key.get_secret_value(),
            timeout_seconds=self._settings.timeout_seconds,
            payload={
                "model": self._settings.model,
                "temperature": 0,
                "max_tokens": self._settings.max_tokens,
                "skip_special_tokens": False,
                "images_config": {"image_mode": image_mode},
                "messages": [{"role": "user", "content": content}],
            },
        )
        if error or body is None:
            return self._failure(error or "empty_response", image_mode=image_mode)

        raw_text, finish_reason = _choice_content(body)
        if finish_reason == "length":
            return self._failure("ocr_output_truncated", image_mode=image_mode)
        if raw_text is None:
            return self._failure("empty_ocr_text", image_mode=image_mode)

        cleaned = clean_ocr_text(raw_text)
        if not cleaned:
            return self._failure("empty_ocr_text", image_mode=image_mode)
        return OcrResult(
            status=JobStatus.SUCCESS,
            text=cleaned,
            model=self._settings.model,
            raw_text=raw_text,
            image_mode=image_mode,
            engine="model",
        )

    def _failure(
        self,
        error: str,
        *,
        image_mode: str | None = None,
    ) -> OcrResult:
        return OcrResult(
            status=JobStatus.FAILURE,
            text=None,
            model=self._settings.model,
            error=error,
            image_mode=image_mode,
            engine="model",
        )


def resolve_image_mode(page_count: int, configured_mode: str) -> str:
    if configured_mode:
        image_mode = configured_mode
    else:
        image_mode = "gundam" if page_count == 1 else "base"
    if page_count > 1 and image_mode not in _MULTI_IMAGE_MODES:
        raise ValueError("gundam and large only support a single image")
    return image_mode


def _choice_content(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, None
    first = choices[0]
    if not isinstance(first, dict):
        return None, None
    finish_reason = first.get("finish_reason")
    reason = finish_reason if isinstance(finish_reason, str) else None
    message = first.get("message")
    if not isinstance(message, dict):
        return None, reason
    content = message.get("content")
    if not isinstance(content, str):
        return None, reason
    cleaned = content.strip()
    return (cleaned or None), reason
