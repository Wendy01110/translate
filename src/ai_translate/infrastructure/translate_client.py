from __future__ import annotations

import httpx

from ai_translate.config import TranslateSettings
from ai_translate.core.models import JobStatus, TranslationRequest, TranslationResult
from ai_translate.infrastructure.openai_compat import message_text, post_chat_completion


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
        if not self._settings.ready:
            return TranslationResult(
                status=JobStatus.FAILURE,
                source_text=request.text,
                translated_text=None,
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                model=self._settings.model,
                error="translate_not_configured",
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

        _, body, error = post_chat_completion(
            self._client,
            base_url=self._settings.base_url,
            api_key=self._settings.api_key.get_secret_value(),
            timeout_seconds=self._settings.timeout_seconds,
            payload={
                "model": self._settings.model,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": request.text},
                ],
                "store": False,
            },
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

        translated = message_text(body)
        if translated is None:
            return TranslationResult(
                status=JobStatus.FAILURE,
                source_text=request.text,
                translated_text=None,
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                model=self._settings.model,
                error="empty_translation",
            )
        return TranslationResult(
            status=JobStatus.SUCCESS,
            source_text=request.text,
            translated_text=translated,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            model=self._settings.model,
        )
