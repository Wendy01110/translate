import pytest

from ai_translate.interfaces.settings import (
    parse_settings_form,
    provider_form,
    settings_window_height,
    should_center_settings,
)


def _form(**overrides: str) -> dict[str, str]:
    payload = {
        "ocr_engine": "auto",
        "ocr_min_confidence": "0.5",
        "ocr_image_mode": "auto",
        "source_lang": "auto",
        "target_lang": "zh",
        "hotkey_selection": "alt+e",
        "hotkey_ocr": "alt+w",
        "translate_model": "m",
        "ocr_model": "Unlimited-OCR",
        "translate_base_url": "https://translate.example/v1",
        "ocr_base_url": "https://ocr.example/v1",
        "translate_api_key": "translate-test-key",
        "ocr_api_key": "ocr-test-key",
        "translate_provider": "openai",
        "translate_region": "",
    }
    payload.update(overrides)
    return payload


def test_parse_settings_form_accepts_ocr_engine_and_hotkeys() -> None:
    prefs = parse_settings_form(
        **_form(
            ocr_engine="vision",
            ocr_min_confidence="0.6",
            source_lang="en",
            hotkey_ocr="option+w",
            translate_model="gpt-4.1-mini",
        )
    )
    assert prefs.ocr_engine == "vision"
    assert prefs.ocr_min_confidence == 0.6
    assert prefs.to_env()["OCR_ENGINE"] == "vision"
    assert prefs.to_env()["TRANSLATE_MODEL"] == "gpt-4.1-mini"
    assert prefs.to_env()["OCR_MODEL"] == "Unlimited-OCR"
    assert prefs.to_env()["TRANSLATE_BASE_URL"] == "https://translate.example/v1"
    assert prefs.to_env()["TRANSLATE_API_KEY"] == "translate-test-key"
    assert prefs.to_env()["OCR_API_KEY"] == "ocr-test-key"
    assert prefs.to_env()["TRANSLATE_PROVIDER"] == "openai"
    assert prefs.hotkey_ocr == "alt+w"


def test_parse_settings_form_accepts_deepl_provider() -> None:
    prefs = parse_settings_form(**_form(translate_provider="deepl", translate_base_url=""))
    assert prefs.translate_provider == "deepl"
    assert prefs.to_env()["TRANSLATE_PROVIDER"] == "deepl"


def test_parse_settings_form_accepts_google_web_without_url() -> None:
    prefs = parse_settings_form(
        **_form(translate_provider="google_web", translate_base_url="", translate_api_key="")
    )
    assert prefs.translate_provider == "google_web"


def test_objc_controller_classes_are_cached_and_uniquely_named() -> None:
    from ai_translate.interfaces.menubar import _menu_controller_class
    from ai_translate.interfaces.settings import _settings_controller_class

    menu = _menu_controller_class()
    settings = _settings_controller_class()
    assert menu is _menu_controller_class()
    assert settings is _settings_controller_class()
    assert menu.__name__ != settings.__name__
    assert menu.__name__ == "AITranslateMenuBarController"
    assert settings.__name__ == "AITranslateSettingsController"


def test_provider_form_hides_key_fields_for_web_sources() -> None:
    web = provider_form("google_web")
    assert web.needs_url is False
    assert web.needs_key is False
    assert web.needs_model is False
    assert web.extra_rows == 0
    openai = provider_form("openai")
    assert openai.needs_url is True
    assert openai.needs_model is True
    assert openai.extra_rows == 3
    assert settings_window_height(extra_rows=0) < settings_window_height(extra_rows=3)


def test_settings_centers_only_when_hidden() -> None:
    assert should_center_settings(visible=False) is True
    assert should_center_settings(visible=True) is False


def test_prepare_settings_window_stays_visible_when_inactive() -> None:
    from ai_translate.interfaces.settings import _prepare_settings_window

    class _Window:
        def __init__(self) -> None:
            self.hides_on_deactivate = True
            self.floating = False
            self.level = None
            self.released = True
            self.collection = None

        def setLevel_(self, value: object) -> None:
            self.level = value

        def setReleasedWhenClosed_(self, value: object) -> None:
            self.released = value

        def setHidesOnDeactivate_(self, value: object) -> None:
            self.hides_on_deactivate = value

        def setFloatingPanel_(self, value: object) -> None:
            self.floating = value

        def setCollectionBehavior_(self, value: object) -> None:
            self.collection = value

    from AppKit import (
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorMoveToActiveSpace,
    )

    window = _Window()
    _prepare_settings_window(window)
    assert window.hides_on_deactivate is False
    assert window.released is False
    assert window.floating is True
    assert window.collection == NSWindowCollectionBehaviorMoveToActiveSpace
    assert window.collection & NSWindowCollectionBehaviorCanJoinAllSpaces == 0


def test_parse_settings_form_rejects_unknown_engine() -> None:
    with pytest.raises(ValueError, match="OCR 方法"):
        parse_settings_form(**_form(ocr_engine="tesseract"))


def test_parse_settings_form_rejects_duplicate_hotkeys() -> None:
    with pytest.raises(ValueError, match="热键不能相同"):
        parse_settings_form(**_form(hotkey_ocr="option+e"))


def test_parse_settings_form_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="翻译来源"):
        parse_settings_form(**_form(translate_provider="youdao"))


def test_parse_settings_form_microsoft_requires_region() -> None:
    with pytest.raises(ValueError, match="区域"):
        parse_settings_form(**_form(translate_provider="microsoft", translate_region=""))


def test_parse_settings_form_rejects_invalid_api_url() -> None:
    with pytest.raises(ValueError, match="http://"):
        parse_settings_form(**_form(translate_base_url="ftp://example"))
