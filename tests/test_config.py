from pydantic import ValidationError
import pytest

from ai_translate.config import (
    HotkeySettings,
    OcrSettings,
    Settings,
    TranslateSettings,
    normalize_api_base_url,
    parse_model_catalog,
    resolve_env_path,
)


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
    assert settings.ocr.model == "Unlimited-OCR"
    assert settings.ocr.api_key.get_secret_value() == ""
    assert settings.ocr.image_mode == ""


def test_web_providers_are_ready_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSLATE_API_KEY", raising=False)
    monkeypatch.delenv("TRANSLATE_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSLATE_MODEL", raising=False)
    for provider in ("google_web", "bing_web", "deepl_web"):
        monkeypatch.setenv("TRANSLATE_PROVIDER", provider)
        assert TranslateSettings(_env_file=None).ready is True


def test_deepl_ready_needs_only_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_PROVIDER", "deepl")
    monkeypatch.setenv("TRANSLATE_API_KEY", "deepl-test-key")
    monkeypatch.delenv("TRANSLATE_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSLATE_MODEL", raising=False)
    settings = TranslateSettings(_env_file=None)
    assert settings.ready is True
    assert settings.provider == "deepl"


def test_microsoft_ready_needs_key_and_region(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_PROVIDER", "microsoft")
    monkeypatch.setenv("TRANSLATE_API_KEY", "ms-test-key")
    monkeypatch.delenv("TRANSLATE_REGION", raising=False)
    assert TranslateSettings(_env_file=None).ready is False
    monkeypatch.setenv("TRANSLATE_REGION", "eastus")
    assert TranslateSettings(_env_file=None).ready is True


def test_blank_model_is_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://translate.example/v1")
    monkeypatch.setenv("TRANSLATE_MODEL", "   ")
    settings = TranslateSettings(_env_file=None)
    assert settings.ready is False


def test_ocr_image_mode_auto_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_IMAGE_MODE", "auto")
    assert OcrSettings(_env_file=None).image_mode == ""


def test_invalid_ocr_engine_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_ENGINE", "tesseract")
    with pytest.raises(ValidationError):
        OcrSettings(_env_file=None)


def test_invalid_ocr_image_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_IMAGE_MODE", "ultra")
    with pytest.raises(ValidationError):
        OcrSettings(_env_file=None)


def test_timeout_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValidationError):
        OcrSettings(_env_file=None)


def test_default_languages_are_auto_to_zh() -> None:
    settings = TranslateSettings(_env_file=None)
    assert settings.source_lang == "auto"
    assert settings.target_lang == "zh"
    assert settings.timeout_seconds == 30.0
    ocr = OcrSettings(_env_file=None)
    assert ocr.timeout_seconds == 180.0
    assert ocr.max_tokens == 24000
    assert ocr.model == "Unlimited-OCR"
    assert ocr.image_mode == ""
    assert ocr.engine == "auto"
    assert ocr.min_confidence == 0.5


def test_ocr_capability_ready_allows_vision_without_model() -> None:
    settings = Settings(
        translate=TranslateSettings(_env_file=None),
        ocr=OcrSettings(_env_file=None),
    )
    assert settings.ocr.model_ready is False
    assert settings.ocr_capability_ready(True) is True
    assert settings.ocr_capability_ready(False) is False


def test_resolve_env_path_prefers_override(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    chosen = tmp_path / "custom.env"
    chosen.write_text("TRANSLATE_MODEL=x\n", encoding="utf-8")
    monkeypatch.setenv("AI_TRANSLATE_ENV_FILE", str(chosen))
    monkeypatch.delenv("AI_TRANSLATE_PROJECT_ROOT", raising=False)
    assert resolve_env_path() == chosen


def test_resolve_env_path_prefers_project_file_over_user_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    user = home / "Library" / "Application Support" / "AI Translate" / ".env"
    project = repo / ".env"
    user.parent.mkdir(parents=True)
    repo.mkdir()
    user.write_text("OCR_MODEL=user-model\n", encoding="utf-8")
    project.write_text("OCR_MODEL=project-model\n", encoding="utf-8")
    monkeypatch.delenv("AI_TRANSLATE_ENV_FILE", raising=False)
    monkeypatch.delenv("AI_TRANSLATE_HOST_NAME", raising=False)
    monkeypatch.setenv("AI_TRANSLATE_PROJECT_ROOT", str(repo))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("ai_translate.config.Path.home", staticmethod(lambda: home))
    assert resolve_env_path() == project


def test_resolve_env_path_uses_user_file_when_project_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    user = home / "Library" / "Application Support" / "AI Translate" / ".env"
    user.parent.mkdir(parents=True)
    repo.mkdir()
    user.write_text("OCR_MODEL=user-model\n", encoding="utf-8")
    monkeypatch.delenv("AI_TRANSLATE_ENV_FILE", raising=False)
    monkeypatch.setenv("AI_TRANSLATE_PROJECT_ROOT", str(repo))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("ai_translate.config.Path.home", staticmethod(lambda: home))
    assert resolve_env_path() == user


def test_resolve_env_path_app_defaults_to_user_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.delenv("AI_TRANSLATE_ENV_FILE", raising=False)
    monkeypatch.setenv("AI_TRANSLATE_PROJECT_ROOT", str(repo))
    monkeypatch.setenv("AI_TRANSLATE_HOST_NAME", "AI Translate")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("ai_translate.config.Path.home", staticmethod(lambda: home))
    assert resolve_env_path() == home / "Library" / "Application Support" / "AI Translate" / ".env"


def test_resolve_env_path_cli_defaults_to_project_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.delenv("AI_TRANSLATE_ENV_FILE", raising=False)
    monkeypatch.delenv("AI_TRANSLATE_HOST_NAME", raising=False)
    monkeypatch.setenv("AI_TRANSLATE_PROJECT_ROOT", str(repo))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("ai_translate.config.Path.home", staticmethod(lambda: home))
    assert resolve_env_path() == repo / ".env"


def test_load_uses_ai_translate_env_file_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_path = tmp_path / "app.env"
    env_path.write_text(
        "TRANSLATE_BASE_URL=https://override.example/v1\nTRANSLATE_MODEL=override-model\n",
        encoding="utf-8",
    )
    for name in (
        "TRANSLATE_BASE_URL",
        "TRANSLATE_MODEL",
        "TRANSLATE_API_KEY",
        "OCR_BASE_URL",
        "OCR_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_TRANSLATE_ENV_FILE", str(env_path))
    settings = Settings.load()
    assert settings.translate.base_url == "https://override.example/v1"
    assert settings.translate.model == "override-model"


def test_preferences_round_trip_ocr_engine() -> None:
    settings = Settings(
        translate=TranslateSettings(_env_file=None),
        ocr=OcrSettings(_env_file=None),
    )
    prefs = settings.preferences()
    assert prefs.ocr_engine == "auto"
    assert prefs.to_env()["OCR_ENGINE"] == "auto"
    assert prefs.to_env()["OCR_MODEL"] == "Unlimited-OCR"
    assert prefs.to_env()["TRANSLATE_MODEL"] == ""
    assert prefs.to_env()["TRANSLATE_BASE_URL"] == ""
    assert prefs.to_env()["TRANSLATE_API_KEY"] == ""
    assert prefs.to_env()["OCR_API_KEY"] == ""


def test_preferences_copy_api_endpoint_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://translate.example/v1")
    monkeypatch.setenv("TRANSLATE_API_KEY", "translate-secret")
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("OCR_API_KEY", "ocr-secret")
    prefs = Settings.load(env_file=None).preferences()
    assert prefs.translate_base_url == "https://translate.example/v1"
    assert prefs.translate_api_key == "translate-secret"
    assert prefs.ocr_api_key == "ocr-secret"
    assert prefs.to_env()["OCR_BASE_URL"] == "https://ocr.example/v1"


def test_normalize_api_base_url_accepts_http_and_empty() -> None:
    assert normalize_api_base_url("", side="翻译") == ""
    assert (
        normalize_api_base_url("https://example/v1", side="翻译")
        == "https://example/v1"
    )
    with pytest.raises(ValueError, match="http://"):
        normalize_api_base_url("example.com", side="翻译")


def test_parse_model_catalog_puts_current_first_and_dedupes() -> None:
    assert parse_model_catalog("b, a, b", "a") == ("b", "a")
    assert parse_model_catalog("a,b", "c") == ("c", "a", "b")
    assert parse_model_catalog("", "") == ()


def test_model_catalog_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_MODEL", "current-translate")
    monkeypatch.setenv("TRANSLATE_MODELS", "alpha, beta")
    monkeypatch.setenv("OCR_MODEL", "current-ocr")
    monkeypatch.setenv("OCR_MODELS", "Unlimited-OCR, other-ocr")
    settings = Settings.load(env_file=None)
    prefs = settings.preferences()
    assert prefs.translate_model == "current-translate"
    assert prefs.translate_model_choices == ("current-translate", "alpha", "beta")
    assert prefs.ocr_model_choices == ("current-ocr", "Unlimited-OCR", "other-ocr")


def test_default_hotkeys_are_alt_e_and_alt_w() -> None:
    hotkey = HotkeySettings(_env_file=None)
    assert hotkey.selection == "alt+e"
    assert hotkey.ocr == "alt+w"
