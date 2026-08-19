from __future__ import annotations

from ai_translate.config import Settings
from ai_translate.core.models import ConfigStatus
from ai_translate.core.ports import OcrEngine, Translator
from ai_translate.features.ocr_translate import OcrTranslateService
from ai_translate.features.selection import SelectionTranslateService
from ai_translate.infrastructure.ocr_client import HttpOcrEngine
from ai_translate.infrastructure.ocr_routing import RoutingOcrEngine
from ai_translate.infrastructure.official_translate import (
    DeepLTranslator,
    GoogleTranslator,
    MicrosoftTranslator,
)
from ai_translate.infrastructure.translate_client import HttpTranslator
from ai_translate.infrastructure.web_translate import (
    BingWebTranslator,
    DeepLWebTranslator,
    GoogleWebTranslator,
)
from ai_translate.infrastructure.vision_ocr import VisionOcrEngine, vision_available


def config_status(settings: Settings) -> ConfigStatus:
    translate = settings.translate
    ocr = settings.ocr
    vision = vision_available()
    return ConfigStatus(
        translate_ready=translate.ready,
        translate_provider=translate.provider,
        translate_base_url=translate.base_url,
        translate_model=translate.model,
        translate_api_key_set=translate.api_key_set,
        translate_source_lang=translate.source_lang,
        translate_target_lang=translate.target_lang,
        ocr_ready=settings.ocr_capability_ready(vision),
        ocr_base_url=ocr.base_url,
        ocr_model=ocr.model,
        ocr_api_key_set=ocr.api_key_set,
        ocr_image_mode=ocr.image_mode or "auto",
        ocr_max_tokens=ocr.max_tokens,
        ocr_engine=ocr.engine,
        ocr_vision_available=vision,
        hotkey_selection=settings.hotkey.selection,
        hotkey_ocr=settings.hotkey.ocr,
        env_file=str(settings.env_file) if settings.env_file else "",
    )


def ocr_engine(settings: Settings) -> OcrEngine:
    local = None
    remote = None
    if settings.ocr.engine != "model" and vision_available():
        local = VisionOcrEngine()
    if settings.ocr.engine != "vision":
        remote = HttpOcrEngine(settings.ocr)
    return RoutingOcrEngine(
        local=local,
        remote=remote,
        mode=settings.ocr.engine,
        min_confidence=settings.ocr.min_confidence,
    )


def translator_for(settings: Settings) -> Translator:
    provider = settings.translate.provider
    if provider == "google_web":
        return GoogleWebTranslator(settings.translate)
    if provider == "bing_web":
        return BingWebTranslator(settings.translate)
    if provider == "deepl_web":
        return DeepLWebTranslator(settings.translate)
    if provider == "deepl":
        return DeepLTranslator(settings.translate)
    if provider == "microsoft":
        return MicrosoftTranslator(settings.translate)
    if provider == "google":
        return GoogleTranslator(settings.translate)
    return HttpTranslator(settings.translate)


def selection_service(settings: Settings) -> SelectionTranslateService:
    return SelectionTranslateService(translator_for(settings))


def ocr_translate_service(settings: Settings) -> OcrTranslateService:
    return OcrTranslateService(
        ocr=ocr_engine(settings),
        translator=translator_for(settings),
    )
