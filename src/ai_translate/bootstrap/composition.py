from __future__ import annotations

from ai_translate.config import Settings
from ai_translate.core.models import ConfigStatus
from ai_translate.features.ocr_translate import OcrTranslateService
from ai_translate.features.selection import SelectionTranslateService
from ai_translate.infrastructure.ocr_client import HttpOcrEngine
from ai_translate.infrastructure.translate_client import HttpTranslator


def config_status(settings: Settings) -> ConfigStatus:
    translate = settings.translate
    ocr = settings.ocr
    return ConfigStatus(
        translate_ready=translate.ready,
        translate_base_url=translate.base_url,
        translate_model=translate.model,
        translate_api_key_set=translate.api_key_set,
        translate_source_lang=translate.source_lang,
        translate_target_lang=translate.target_lang,
        ocr_ready=ocr.ready,
        ocr_base_url=ocr.base_url,
        ocr_model=ocr.model,
        ocr_api_key_set=ocr.api_key_set,
    )


def selection_service(settings: Settings) -> SelectionTranslateService:
    return SelectionTranslateService(HttpTranslator(settings.translate))


def ocr_translate_service(settings: Settings) -> OcrTranslateService:
    return OcrTranslateService(
        ocr=HttpOcrEngine(settings.ocr),
        translator=HttpTranslator(settings.translate),
    )
