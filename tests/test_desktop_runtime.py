from types import SimpleNamespace

import pytest

import ai_translate.app as app
import ai_translate.bootstrap.composition as composition
from ai_translate.config import (
    HotkeySettings,
    LocalAdvancedOcrSettings,
    OcrSettings,
    Settings,
    StandardOcrSettings,
    TranslateSettings,
)
from ai_translate.infrastructure.paddle_ocr import PaddleOcrEngine
from tests.support import FakeTranslator


def _settings(**changes) -> Settings:
    defaults = {
        "translate": TranslateSettings.model_construct(provider="openai", model="fake"),
        "ocr": OcrSettings.model_construct(engine="paddle"),
        "standard_ocr": StandardOcrSettings.model_construct(),
        "local_advanced_ocr": LocalAdvancedOcrSettings.model_construct(),
        "hotkey": HotkeySettings.model_construct(),
    }
    defaults.update(changes)
    return Settings(**defaults)


@pytest.fixture
def runtime(monkeypatch):
    initialized = []
    translators = []
    notices = []

    class Pipeline:
        def predict(self, _image):
            return [{"rec_texts": ["Synthetic sample"], "rec_scores": [0.99]}]

    def pipeline_factory(**options):
        initialized.append(options["text_detection_model_name"])
        return Pipeline()

    def make_ocr(settings, *, on_first_load=None):
        return PaddleOcrEngine(
            settings,
            factory=pipeline_factory,
            decoder=lambda _image: object(),
            on_first_load=on_first_load,
        )

    def make_translator(settings):
        translator = FakeTranslator(model=settings.translate.model)
        translators.append(translator)
        return translator

    monkeypatch.setattr(composition, "vision_available", lambda: False)
    monkeypatch.setattr(composition, "paddle_ocr_available", lambda: True)
    monkeypatch.setattr(composition, "PaddleOcrEngine", make_ocr)
    monkeypatch.setattr(composition, "translator_for", make_translator)
    services = composition.DesktopRuntime(_settings(), on_paddle_first_load=notices.append)
    return services, initialized, translators, notices


def test_language_hotkeys_and_catalog_changes_keep_loaded_pipeline(runtime) -> None:
    services, initialized, translators, notices = runtime
    first_selection = services.selection
    first_ocr_translate = services.ocr_translate
    services.ocr_translate.translate_image(b"synthetic", "image/png", "auto", "zh")

    for settings in (
        _settings(),
        _settings(translate=TranslateSettings.model_construct(
            provider="openai", model="fake", source_lang="en", target_lang="ja", models="a,b",
        )),
        _settings(hotkey=HotkeySettings.model_construct(selection="ctrl+e")),
        _settings(ocr=OcrSettings.model_construct(engine="paddle", models="new-catalog")),
    ):
        services.update(settings)
        services.ocr_translate.translate_image(b"synthetic", "image/png", "auto", "zh")
        assert services.selection is first_selection
        assert services.ocr_translate is first_ocr_translate

    services.selection.translate_text("Synthetic text", "auto", "zh")
    assert initialized == ["PP-OCRv6_tiny_det"]
    assert notices == ["PP-OCRv6_tiny"]
    assert len(translators) == 1
    assert len(translators[0].calls) == 6


def test_translate_change_keeps_ocr_and_ocr_change_keeps_translator(runtime) -> None:
    services, initialized, translators, notices = runtime
    services.ocr_translate.translate_image(b"synthetic", "image/png", "auto", "zh")
    settings = _settings(translate=TranslateSettings.model_construct(provider="openai", model="new"))
    services.update(settings)
    translated = services.ocr_translate.translate_image(b"synthetic", "image/png", "auto", "zh")
    assert translated.translate_model == "new"
    assert len(translators) == 2
    assert initialized == ["PP-OCRv6_tiny_det"]
    selection = services.selection

    services.update(_settings(
        translate=settings.translate,
        local_advanced_ocr=LocalAdvancedOcrSettings.model_construct(model_tier="small"),
    ))
    recognized = services.ocr_translate.translate_image(b"synthetic", "image/png", "auto", "zh")
    assert recognized.ocr_model == "PP-OCRv6_small"
    assert services.selection is selection
    assert len(translators) == 2
    assert initialized == ["PP-OCRv6_tiny_det", "PP-OCRv6_small_det"]
    assert notices == ["PP-OCRv6_tiny", "PP-OCRv6_small"]


def test_save_preferences_reuses_runtime_and_updates_listener(monkeypatch, runtime) -> None:
    services, initialized, translators, _notices = runtime
    services.ocr_translate.translate_image(b"synthetic", "image/png", "auto", "zh")
    before = services.ocr_translate
    settings = _settings(translate=TranslateSettings.model_construct(
        provider="openai", model="fake", target_lang="ja",
    ))
    written = []
    applied = []
    languages = []
    monkeypatch.setattr(app, "resolve_env_path", lambda: "synthetic.env")
    monkeypatch.setattr(app, "upsert_env_values", lambda _path, values: written.append(values))
    monkeypatch.setattr(app.Settings, "load", lambda: settings)

    app._save_preferences(
        settings.preferences(),
        listener=SimpleNamespace(replace_runtime=lambda **values: applied.append(values)),
        presenter=SimpleNamespace(set_target_language=languages.append),
        services=services,
    )
    services.ocr_translate.translate_image(b"synthetic", "image/png", "auto", "ja")
    assert services.ocr_translate is before
    assert initialized == ["PP-OCRv6_tiny_det"]
    assert len(translators) == 1
    assert written[0]["TRANSLATE_TARGET_LANG"] == "ja"
    assert applied[0]["ocr_translate"] is before
    assert applied[0]["target_lang"] == "ja"
    assert languages == ["ja"]
