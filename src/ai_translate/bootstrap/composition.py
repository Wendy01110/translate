from __future__ import annotations

from collections.abc import Callable

from ai_translate.config import Settings
from ai_translate.core.models import ConfigStatus
from ai_translate.core.ports import OcrEngine, Translator
from ai_translate.features.ocr_translate import OcrTranslateService
from ai_translate.features.selection import SelectionTranslateService
from ai_translate.infrastructure.ocr_client import HttpOcrEngine
from ai_translate.infrastructure.ocr_routing import (
    RoutingOcrEngine,
    TieredLocalOcrEngine,
    TieredRemoteOcrEngine,
)
from ai_translate.infrastructure.ocr_space import (
    OCR_SPACE_MAX_IMAGE_BYTES,
    OcrSpaceEngine,
)
from ai_translate.infrastructure.official_translate import (
    DeepLTranslator,
    GoogleTranslator,
    MicrosoftTranslator,
)
from ai_translate.infrastructure.paddle_ocr import (
    PaddleOcrEngine,
    paddle_ocr_available,
)
from ai_translate.infrastructure.translate_client import HttpTranslator
from ai_translate.infrastructure.web_translate import (
    BingWebTranslator,
    DeepLWebTranslator,
    GoogleWebTranslator,
)
from ai_translate.infrastructure.vision_ocr import VisionOcrEngine, vision_available


class DesktopRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        on_paddle_first_load: Callable[[str], None] | None = None,
    ) -> None:
        self._settings: Settings | None = None
        self._on_paddle_first_load = on_paddle_first_load
        self.update(settings)

    def update(self, settings: Settings) -> None:
        previous = self._settings
        language_and_catalog = {"source_lang", "target_lang", "models"}
        translate_changed = previous is None or (
            settings.translate.model_dump(exclude=language_and_catalog)
            != previous.translate.model_dump(exclude=language_and_catalog)
        )
        ocr_changed = previous is None or (
            settings.ocr.model_dump(exclude={"models"})
            != previous.ocr.model_dump(exclude={"models"})
            or settings.standard_ocr != previous.standard_ocr
            or settings.local_advanced_ocr != previous.local_advanced_ocr
        )
        translator = translator_for(settings) if translate_changed else self._translator
        ocr = (
            ocr_engine(settings, on_paddle_first_load=self._on_paddle_first_load)
            if ocr_changed
            else self._ocr
        )
        if translate_changed:
            self.selection = SelectionTranslateService(translator)
        if translate_changed or ocr_changed:
            self.ocr_translate = OcrTranslateService(ocr, translator)
        self._translator = translator
        self._ocr = ocr
        self._settings = settings


def config_status(settings: Settings) -> ConfigStatus:
    translate = settings.translate
    ocr = settings.ocr
    vision = vision_available()
    paddle = paddle_ocr_available()
    return ConfigStatus(
        translate_ready=translate.ready,
        translate_provider=translate.provider,
        translate_base_url=translate.base_url,
        translate_model=translate.model,
        translate_router_thinking=translate.router_thinking_for_request,
        translate_api_key_set=translate.api_key_set,
        translate_source_lang=translate.source_lang,
        translate_target_lang=translate.target_lang,
        ocr_ready=settings.ocr_capability_ready(vision, paddle),
        ocr_base_url=ocr.base_url,
        ocr_model=ocr.model,
        ocr_api_key_set=ocr.api_key_set,
        ocr_image_mode=ocr.image_mode or "auto",
        ocr_max_tokens=ocr.max_tokens,
        ocr_engine=ocr.engine,
        ocr_vision_available=vision,
        ocr_local_advanced_available=paddle,
        ocr_local_advanced_model=settings.local_advanced_ocr.model,
        hotkey_selection=settings.hotkey.selection,
        hotkey_ocr=settings.hotkey.ocr,
        hotkey_live_ocr=settings.hotkey.live_ocr,
        env_file=str(settings.env_file) if settings.env_file else "",
        ocr_standard_ready=settings.standard_ocr.ready,
        ocr_standard_base_url=settings.standard_ocr.base_url,
        ocr_standard_api_key_set=settings.standard_ocr.api_key_set,
        ocr_standard_engine=settings.standard_ocr.engine,
        ocr_standard_max_image_bytes=OCR_SPACE_MAX_IMAGE_BYTES,
        ocr_advanced_ready=ocr.model_ready,
        ocr_router_thinking=ocr.router_thinking_for_request,
    )


def ocr_engine(
    settings: Settings,
    *,
    on_paddle_first_load: Callable[[str], None] | None = None,
) -> OcrEngine:
    local = None
    remote = None
    mode = settings.ocr.engine
    vision = (
        VisionOcrEngine()
        if mode in {"auto", "vision"} and vision_available()
        else None
    )
    paddle = (
        PaddleOcrEngine(
            settings.local_advanced_ocr,
            on_first_load=on_paddle_first_load,
        )
        if mode in {"auto", "paddle"} and paddle_ocr_available()
        else None
    )
    if mode == "vision":
        local = vision
    elif mode == "paddle":
        local = paddle
    elif mode == "auto" and (vision is not None or paddle is not None):
        local = TieredLocalOcrEngine(
            standard=vision,
            advanced=paddle,
            min_confidence=settings.ocr.min_confidence,
        )
    if mode == "standard":
        remote = OcrSpaceEngine(settings.standard_ocr)
    elif mode == "model":
        remote = HttpOcrEngine(settings.ocr)
    elif mode == "auto":
        standard = (
            OcrSpaceEngine(settings.standard_ocr)
            if settings.standard_ocr.ready
            else None
        )
        advanced = HttpOcrEngine(settings.ocr) if settings.ocr.model_ready else None
        if standard is not None or advanced is not None:
            remote = TieredRemoteOcrEngine(
                standard=standard,
                advanced=advanced,
            )
    return RoutingOcrEngine(
        local=local,
        remote=remote,
        mode=mode,
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


def ocr_translate_service(
    settings: Settings,
    *,
    on_paddle_first_load: Callable[[str], None] | None = None,
) -> OcrTranslateService:
    return OcrTranslateService(
        ocr=ocr_engine(
            settings,
            on_paddle_first_load=on_paddle_first_load,
        ),
        translator=translator_for(settings),
    )
