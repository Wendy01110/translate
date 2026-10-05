from __future__ import annotations

import httpx

from ai_translate.config import TranslateSettings
from ai_translate.core.limits import MAX_TRANSLATION_CHARS
from ai_translate.core.models import JobStatus, TranslationRequest, TranslationResult
from ai_translate.infrastructure.openai_compat import (
    completion_content,
    post_chat_completion,
)


class HttpTranslator:
    def __init__(
        self,
        settings: TranslateSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        if not self._settings.ready or len(request.text) > MAX_TRANSLATION_CHARS:
            return TranslationResult(
                status=JobStatus.FAILURE,
                source_text=request.text,
                translated_text=None,
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                model=self._settings.model,
                error=(
                    "translate_not_configured"
                    if not self._settings.ready
                    else "text_too_long"
                ),
            )

        if request.source_lang == "auto":
            instruction = (
                "You are a translator. Detect the source language and translate "
                f"the user's text into {request.target_lang}. "
                "Return only the translation, with no quotes or commentary."
            )
        else:
            instruction = (
                "You are a translator. Translate the user's text from "
                f"{request.source_lang} to {request.target_lang}. "
                "Return only the translation, with no quotes or commentary."
            )

        payload = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": request.text},
            ],
            "store": False,
        }
        router_thinking = self._settings.router_thinking_for_request
        if router_thinking is not None:
            payload["router"] = {"thinking": router_thinking}

        _, body, error = post_chat_completion(
            self._client,
            base_url=self._settings.base_url,
            api_key=self._settings.api_key.get_secret_value(),
            timeout_seconds=self._settings.timeout_seconds,
            payload=payload,
        )
        if error or body is None:
            return TranslationResult(
                status=JobStatus.FAILURE,
                source_text=request.text,
                translated_text=None,
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                model=self._settings.model,
                error=error or "empty_response",
            )

        translated, finish_reason = completion_content(body)
        if finish_reason == "length" or translated is None:
            return TranslationResult(
                status=JobStatus.FAILURE,
                source_text=request.text,
                translated_text=None,
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                model=self._settings.model,
                error=(
                    "translate_output_truncated"
                    if finish_reason == "length"
                    else "empty_translation"
                ),
            )
        return TranslationResult(
            status=JobStatus.SUCCESS,
            source_text=request.text,
            translated_text=translated,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            model=self._settings.model,
        )
