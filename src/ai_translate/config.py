from __future__ import annotations

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    timeout_seconds: float = Field(default=30.0, gt=0)
    source_lang: str = "auto"
    target_lang: str = "zh"

    @field_validator("base_url", "model", "source_lang", "target_lang", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @property
    def ready(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key.get_secret_value())


class OcrSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OCR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = ""
    api_key: SecretStr = SecretStr("")
    model: str = ""
    timeout_seconds: float = Field(default=60.0, gt=0)

    @field_validator("base_url", "model", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @property
    def ready(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def api_key_set(self) -> bool:
        return bool(self.api_key.get_secret_value())


class Settings:
    def __init__(self, translate: TranslateSettings, ocr: OcrSettings) -> None:
        self.translate = translate
        self.ocr = ocr

    @classmethod
    def load(cls, *, env_file: str | None = ".env") -> Settings:
        return cls(
            translate=TranslateSettings(_env_file=env_file),
            ocr=OcrSettings(_env_file=env_file),
        )

    @property
    def translate_ready(self) -> bool:
        return self.translate.ready

    @property
    def ocr_ready(self) -> bool:
        return self.ocr.ready
