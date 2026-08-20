from __future__ import annotations

from ai_translate.bootstrap.composition import (
    config_status,
    ocr_engine,
    ocr_translate_service,
)
from ai_translate.config import (
    LocalAdvancedOcrSettings,
    OcrSettings,
    Settings,
    StandardOcrSettings,
    TranslateSettings,
)
from tests.support import FakeOcrEngine


def _settings(*, mode: str = "auto") -> Settings:
    return Settings(
        translate=TranslateSettings(_env_file=None),
        ocr=OcrSettings(
            base_url="https://advanced.example/v1",
            model="advanced-model",
            engine=mode,
            _env_file=None,
        ),
        standard_ocr=StandardOcrSettings(
            api_key="standard-secret",
            _env_file=None,
        ),
        local_advanced_ocr=LocalAdvancedOcrSettings(_env_file=None),
    )


def test_auto_composes_standard_before_advanced(monkeypatch) -> None:
    standard = FakeOcrEngine(text="from-standard")
    advanced = FakeOcrEngine(text="from-advanced")
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.vision_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.paddle_ocr_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.OcrSpaceEngine",
        lambda _settings: standard,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.HttpOcrEngine",
        lambda _settings: advanced,
    )

    result = ocr_engine(_settings()).recognize(b"png", "image/png")
    assert result.text == "from-standard"
    assert standard.calls
    assert advanced.calls == []


def test_standard_mode_does_not_construct_advanced(monkeypatch) -> None:
    standard = FakeOcrEngine(text="from-standard")

    def advanced_not_constructed(_settings) -> FakeOcrEngine:
        raise AssertionError("advanced constructed")

    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.vision_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.paddle_ocr_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.OcrSpaceEngine",
        lambda _settings: standard,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.HttpOcrEngine",
        advanced_not_constructed,
    )
    result = ocr_engine(_settings(mode="standard")).recognize(b"png", "image/png")
    assert result.text == "from-standard"


def test_model_mode_does_not_construct_standard(monkeypatch) -> None:
    advanced = FakeOcrEngine(text="from-advanced")

    def standard_not_constructed(_settings) -> FakeOcrEngine:
        raise AssertionError("standard constructed")

    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.vision_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.paddle_ocr_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.OcrSpaceEngine",
        standard_not_constructed,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.HttpOcrEngine",
        lambda _settings: advanced,
    )
    result = ocr_engine(_settings(mode="model")).recognize(b"png", "image/png")
    assert result.text == "from-advanced"


def test_config_status_reports_standard_and_advanced_independently(monkeypatch) -> None:
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.vision_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.paddle_ocr_available",
        lambda: False,
    )
    status = config_status(_settings())
    assert status.ocr_ready is True
    assert status.ocr_standard_ready is True
    assert status.ocr_advanced_ready is True
    assert status.ocr_standard_api_key_set is True
    assert status.ocr_api_key_set is False
    assert status.ocr_local_advanced_available is False


def test_auto_composes_paddle_before_api_on_windows_like_host(monkeypatch) -> None:
    paddle = FakeOcrEngine(text="from-paddle", model="PP-OCRv6_small")
    standard = FakeOcrEngine(text="from-api-standard")
    captured_notifier = None

    def build_paddle(_settings, *, on_first_load=None):
        nonlocal captured_notifier
        captured_notifier = on_first_load
        return paddle

    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.vision_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.paddle_ocr_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.PaddleOcrEngine",
        build_paddle,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.OcrSpaceEngine",
        lambda _settings: standard,
    )

    notifier = lambda _model: None
    result = ocr_engine(
        _settings(),
        on_paddle_first_load=notifier,
    ).recognize(b"png", "image/png")

    assert result.text == "from-paddle"
    assert paddle.calls
    assert standard.calls == []
    assert captured_notifier is notifier


def test_paddle_first_load_notifier_is_optional_for_non_desktop_paths(
    monkeypatch,
) -> None:
    paddle = FakeOcrEngine(text="from-paddle")
    captured_notifiers = []

    def build_paddle(_settings, *, on_first_load=None):
        captured_notifiers.append(on_first_load)
        return paddle

    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.paddle_ocr_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.PaddleOcrEngine",
        build_paddle,
    )

    ocr_engine(_settings(mode="paddle"))

    assert captured_notifiers == [None]


def test_ocr_translate_service_forwards_paddle_first_load_notifier(
    monkeypatch,
) -> None:
    captured_notifier = None
    fake_ocr = FakeOcrEngine(text="from-paddle")

    def build_ocr(_settings, *, on_paddle_first_load=None):
        nonlocal captured_notifier
        captured_notifier = on_paddle_first_load
        return fake_ocr

    monkeypatch.setattr(
        "ai_translate.bootstrap.composition.ocr_engine",
        build_ocr,
    )
    notifier = lambda _model: None

    service = ocr_translate_service(
        _settings(),
        on_paddle_first_load=notifier,
    )

    assert service is not None
    assert captured_notifier is notifier
