from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_translate.core.hotkeys import format_hotkey_spec, parse_hotkey


class TranslateSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRANSLATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = ""
    api_key: SecretStr = SecretStr("")
    model: str = ""
    models: str = ""
    provider: str = "google_web"
    region: str = ""
    timeout_seconds: float = Field(default=30.0, gt=0)
    source_lang: str = "auto"
    target_lang: str = "zh"

    @field_validator(
        "base_url",
        "model",
        "models",
        "region",
        "source_lang",
        "target_lang",
        mode="before",
    )
    @classmethod
    def _strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        if cleaned not in TRANSLATE_PROVIDERS:
            raise ValueError(
                "TRANSLATE_PROVIDER must be openai, deepl, microsoft, google, "
                "google_web, bing_web, or deepl_web"
            )
        return cleaned

    @property
    def ready(self) -> bool:
        if self.provider == "deepl":
            return self.api_key_set
        if self.provider == "microsoft":
            return self.api_key_set and bool(self.region)
        if self.provider == "google":
            return self.api_key_set
        if self.provider in {"google_web", "bing_web", "deepl_web"}:
            return True
        return bool(self.base_url and self.model)

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key.get_secret_value())


OCR_IMAGE_MODES = frozenset({"tiny", "small", "base", "large", "gundam"})
OCR_ENGINES = frozenset({"auto", "vision", "paddle", "standard", "model"})
PADDLE_OCR_MODEL_TIERS = frozenset({"tiny", "small", "medium"})
TRANSLATE_PROVIDERS = frozenset(
    {
        "openai",
        "deepl",
        "microsoft",
        "google",
        "google_web",
        "bing_web",
        "deepl_web",
    }
)
_OCR_IMAGE_MODES = OCR_IMAGE_MODES
_OCR_ENGINES = OCR_ENGINES
_PADDLE_OCR_MODEL_TIERS = PADDLE_OCR_MODEL_TIERS
_TRANSLATE_PROVIDERS = TRANSLATE_PROVIDERS


def user_env_path() -> Path:
    if sys.platform == "win32":
        appdata = (os.environ.get("APPDATA") or "").strip()
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "AI Translate" / ".env"
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "AI Translate"
        / ".env"
    )


def project_env_path() -> Path:
    root = (os.environ.get("AI_TRANSLATE_PROJECT_ROOT") or "").strip()
    if root:
        return Path(root) / ".env"
    return Path.cwd() / ".env"


def resolve_env_path() -> Path:
    override = (os.environ.get("AI_TRANSLATE_ENV_FILE") or "").strip()
    if override:
        return Path(override).expanduser()
    project = project_env_path()
    if project.exists():
        return project
    user = user_env_path()
    if user.exists():
        return user
    if (os.environ.get("AI_TRANSLATE_HOST_NAME") or "").strip():
        return user
    return project


def normalize_api_base_url(value: str, *, side: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if any(ch.isspace() for ch in cleaned):
        raise ValueError(f"{side} API 地址不能包含空白")
    lowered = cleaned.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise ValueError(f"{side} API 地址必须以 http:// 或 https:// 开头")
    return cleaned


def parse_model_catalog(raw: str, current: str) -> tuple[str, ...]:
    items: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        name = part.strip()
        if not name or name in seen:
            continue
        items.append(name)
        seen.add(name)
    current_name = current.strip()
    if current_name and current_name not in seen:
        items.insert(0, current_name)
    return tuple(items)


@dataclass(frozen=True)
class AppPreferences:
    ocr_engine: str
    ocr_local_advanced_model_tier: str
    ocr_min_confidence: float
    ocr_image_mode: str
    source_lang: str
    target_lang: str
    hotkey_selection: str
    hotkey_ocr: str
    hotkey_live_ocr: str
    translate_model: str
    ocr_model: str
    translate_base_url: str
    ocr_base_url: str
    translate_api_key: str
    ocr_api_key: str
    ocr_standard_api_key: str
    translate_provider: str = "google_web"
    translate_region: str = ""
    translate_model_choices: tuple[str, ...] = ()
    ocr_model_choices: tuple[str, ...] = ()

    def to_env(self) -> dict[str, str]:
        mode = self.ocr_image_mode or "auto"
        return {
            "OCR_ENGINE": self.ocr_engine,
            "OCR_LOCAL_ADVANCED_MODEL_TIER": self.ocr_local_advanced_model_tier,
            "OCR_MIN_CONFIDENCE": f"{self.ocr_min_confidence:g}",
            "OCR_IMAGE_MODE": mode,
            "TRANSLATE_SOURCE_LANG": self.source_lang,
            "TRANSLATE_TARGET_LANG": self.target_lang,
            "TRANSLATE_PROVIDER": self.translate_provider,
            "TRANSLATE_BASE_URL": self.translate_base_url,
            "TRANSLATE_MODEL": self.translate_model,
            "TRANSLATE_API_KEY": self.translate_api_key,
            "TRANSLATE_REGION": self.translate_region,
            "OCR_BASE_URL": self.ocr_base_url,
            "OCR_MODEL": self.ocr_model,
            "OCR_API_KEY": self.ocr_api_key,
            "OCR_STANDARD_API_KEY": self.ocr_standard_api_key,
            "HOTKEY_SELECTION": self.hotkey_selection,
            "HOTKEY_OCR": self.hotkey_ocr,
            "HOTKEY_LIVE_OCR": self.hotkey_live_ocr,
        }


class OcrSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OCR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = ""
    api_key: SecretStr = SecretStr("")
    model: str = "Unlimited-OCR"
    models: str = ""
    timeout_seconds: float = Field(default=180.0, gt=0)
    max_tokens: int = Field(default=24000, gt=0)
    image_mode: str = ""
    engine: str = "auto"
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("base_url", "model", "models", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("image_mode", mode="before")
    @classmethod
    def _normalize_image_mode(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        if cleaned in {"", "auto"}:
            return ""
        if cleaned not in _OCR_IMAGE_MODES:
            raise ValueError(
                "OCR_IMAGE_MODE must be auto, tiny, small, base, large, or gundam"
            )
        return cleaned

    @field_validator("engine", mode="before")
    @classmethod
    def _normalize_engine(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        if cleaned not in _OCR_ENGINES:
            raise ValueError(
                "OCR_ENGINE must be auto, vision, paddle, standard, or model"
            )
        return cleaned

    @property
    def model_ready(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def ready(self) -> bool:
        return self.model_ready

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key.get_secret_value())


class StandardOcrSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OCR_STANDARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "https://api.ocr.space/parse/image"
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=30.0, gt=0)
    engine: int = Field(default=2, ge=1, le=3)
    language: str = "auto"

    @field_validator("base_url", mode="before")
    @classmethod
    def _normalize_base_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return normalize_api_base_url(value, side="普通 OCR")

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_language(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        if cleaned != "auto" and (len(cleaned) != 3 or not cleaned.isalpha()):
            raise ValueError("OCR_STANDARD_LANGUAGE must be auto or a 3-letter code")
        return cleaned

    @property
    def ready(self) -> bool:
        return bool(self.base_url and self.api_key_set)

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key.get_secret_value())


class LocalAdvancedOcrSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OCR_LOCAL_ADVANCED_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_tier: str = "tiny"
    device: str = "cpu"

    @field_validator("model_tier", mode="before")
    @classmethod
    def _normalize_model_tier(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        if cleaned not in _PADDLE_OCR_MODEL_TIERS:
            raise ValueError(
                "OCR_LOCAL_ADVANCED_MODEL_TIER must be tiny, small, or medium"
            )
        return cleaned

    @field_validator("device", mode="before")
    @classmethod
    def _normalize_device(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        if cleaned != "cpu":
            raise ValueError("OCR_LOCAL_ADVANCED_DEVICE currently only supports cpu")
        return cleaned

    @property
    def model(self) -> str:
        return f"PP-OCRv6_{self.model_tier}"


class HotkeySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOTKEY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    selection: str = "alt+e"
    ocr: str = "alt+w"
    live_ocr: str = "alt+q"

    @field_validator("selection", "ocr", "live_ocr", mode="before")
    @classmethod
    def _normalize_hotkey(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return format_hotkey_spec(parse_hotkey(value.strip().lower()))

    @model_validator(mode="after")
    def _reject_duplicate_hotkeys(self) -> HotkeySettings:
        parsed = {
            parse_hotkey(self.selection),
            parse_hotkey(self.ocr),
            parse_hotkey(self.live_ocr),
        }
        if len(parsed) != 3:
            raise ValueError("selection, OCR, and live OCR hotkeys must be different")
        return self


class Settings:
    def __init__(
        self,
        translate: TranslateSettings,
        ocr: OcrSettings,
        standard_ocr: StandardOcrSettings | None = None,
        local_advanced_ocr: LocalAdvancedOcrSettings | None = None,
        hotkey: HotkeySettings | None = None,
        env_file: str | None = None,
    ) -> None:
        self.translate = translate
        self.ocr = ocr
        self.standard_ocr = standard_ocr or StandardOcrSettings(_env_file=None)
        self.local_advanced_ocr = local_advanced_ocr or LocalAdvancedOcrSettings(
            _env_file=None
        )
        self.hotkey = hotkey or HotkeySettings(_env_file=None)
        self.env_file = env_file

    @classmethod
    def load(cls, *, env_file: str | None = ".env") -> Settings:
        if env_file is None:
            chosen = None
        elif env_file == ".env":
            chosen = str(resolve_env_path())
        else:
            chosen = env_file
        return cls(
            translate=TranslateSettings(_env_file=chosen),
            ocr=OcrSettings(_env_file=chosen),
            standard_ocr=StandardOcrSettings(_env_file=chosen),
            local_advanced_ocr=LocalAdvancedOcrSettings(_env_file=chosen),
            hotkey=HotkeySettings(_env_file=chosen),
            env_file=chosen,
        )

    def preferences(self) -> AppPreferences:
        return AppPreferences(
            ocr_engine=self.ocr.engine,
            ocr_local_advanced_model_tier=self.local_advanced_ocr.model_tier,
            ocr_min_confidence=self.ocr.min_confidence,
            ocr_image_mode=self.ocr.image_mode or "auto",
            source_lang=self.translate.source_lang,
            target_lang=self.translate.target_lang,
            hotkey_selection=self.hotkey.selection,
            hotkey_ocr=self.hotkey.ocr,
            hotkey_live_ocr=self.hotkey.live_ocr,
            translate_model=self.translate.model,
            ocr_model=self.ocr.model,
            translate_base_url=self.translate.base_url,
            ocr_base_url=self.ocr.base_url,
            translate_api_key=self.translate.api_key.get_secret_value(),
            ocr_api_key=self.ocr.api_key.get_secret_value(),
            ocr_standard_api_key=self.standard_ocr.api_key.get_secret_value(),
            translate_provider=self.translate.provider,
            translate_region=self.translate.region,
            translate_model_choices=parse_model_catalog(
                self.translate.models,
                self.translate.model,
            ),
            ocr_model_choices=parse_model_catalog(self.ocr.models, self.ocr.model),
        )

    @property
    def translate_ready(self) -> bool:
        return self.translate.ready

    @property
    def ocr_ready(self) -> bool:
        return self.standard_ocr.ready or self.ocr.model_ready

    def ocr_capability_ready(
        self,
        vision_available: bool,
        paddle_available: bool = False,
    ) -> bool:
        if self.ocr.engine == "model":
            return self.ocr.model_ready
        if self.ocr.engine == "standard":
            return self.standard_ocr.ready
        if self.ocr.engine == "paddle":
            return paddle_available
        if self.ocr.engine == "vision":
            return vision_available
        return (
            vision_available
            or paddle_available
            or self.standard_ocr.ready
            or self.ocr.model_ready
        )
