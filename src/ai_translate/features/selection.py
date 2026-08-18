from __future__ import annotations

from ai_translate.core.models import (
    JobKind,
    JobStatus,
    TranslateJob,
    TranslationRequest,
)
from ai_translate.core.ports import Translator


class SelectionTranslateService:
    def __init__(self, translator: Translator) -> None:
        self._translator = translator

    def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslateJob:
        cleaned = text.strip()
        if not cleaned:
            return TranslateJob(
                kind=JobKind.SELECTION,
                status=JobStatus.FAILURE,
                source_text=text,
                translated_text=None,
                error="empty_text",
            )

        result = self._translator.translate(
            TranslationRequest(
                text=cleaned,
                source_lang=source_lang,
                target_lang=target_lang,
            )
        )
        return TranslateJob(
            kind=JobKind.SELECTION,
            status=result.status,
            source_text=result.source_text,
            translated_text=result.translated_text,
            error=result.error,
            translate_model=result.model,
        )
