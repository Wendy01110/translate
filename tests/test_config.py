from pydantic import ValidationError
import pytest

from ai_translate.config import OcrSettings, Settings, TranslateSettings


def test_translate_and_ocr_use_separate_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://translate.example/v1")
    monkeypatch.setenv("TRANSLATE_API_KEY", "translate-secret")
    monkeypatch.setenv("TRANSLATE_MODEL", "translate-model")
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("OCR_API_KEY", "ocr-secret")
    monkeypatch.setenv("OCR_MODEL", "ocr-model")

    settings = Settings.load(env_file=None)

    assert settings.translate_ready is True
    assert settings.ocr_ready is True
    assert settings.translate.base_url == "https://translate.example/v1"
    assert settings.translate.model == "translate-model"
    assert settings.translate.api_key.get_secret_value() == "translate-secret"
    assert settings.ocr.base_url == "https://ocr.example/v1"
    assert settings.ocr.model == "ocr-model"
    assert settings.ocr.api_key.get_secret_value() == "ocr-secret"
    assert settings.translate.api_key.get_secret_value() != settings.ocr.api_key.get_secret_value()


def test_one_side_does_not_inherit_the_other_side(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://translate.example/v1")
    monkeypatch.setenv("TRANSLATE_MODEL", "translate-model")
    monkeypatch.setenv("TRANSLATE_API_KEY", "translate-secret")
    monkeypatch.delenv("OCR_BASE_URL", raising=False)
    monkeypatch.delenv("OCR_MODEL", raising=False)
    monkeypatch.delenv("OCR_API_KEY", raising=False)

    settings = Settings.load(env_file=None)

    assert settings.translate_ready is True
    assert settings.ocr_ready is False
    assert settings.ocr.base_url == ""
    assert settings.ocr.model == ""
    assert settings.ocr.api_key.get_secret_value() == ""


def test_blank_model_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://translate.example/v1")
    monkeypatch.setenv("TRANSLATE_MODEL", "   ")
    settings = TranslateSettings(_env_file=None)
    assert settings.ready is False


def test_timeout_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValidationError):
        OcrSettings(_env_file=None)


def test_default_languages_are_auto_to_zh() -> None:
    settings = TranslateSettings(_env_file=None)
    assert settings.source_lang == "auto"
    assert settings.target_lang == "zh"
    assert settings.timeout_seconds == 30.0
    assert OcrSettings(_env_file=None).timeout_seconds == 60.0
