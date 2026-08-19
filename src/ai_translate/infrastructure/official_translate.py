from __future__ import annotations

import html
from typing import Any
from urllib.parse import urlencode

import httpx

from ai_translate.config import TranslateSettings
from ai_translate.core.models import JobStatus, TranslationRequest, TranslationResult

_MAX_TEXT_CHARS = 8000
_DEEPL_DEFAULT = "https://api-free.deepl.com"
_MICROSOFT_DEFAULT = "https://api.cognitive.microsofttranslator.com"
_GOOGLE_DEFAULT = "https://translation.googleapis.com/language/translate/v2"
_DEEPL_LANG = {"en": "EN", "zh": "ZH", "ja": "JA", "ko": "KO"}
_MICROSOFT_LANG = {"en": "en", "zh": "zh-Hans", "ja": "ja", "ko": "ko"}
_GOOGLE_LANG = {"en": "en", "zh": "zh-CN", "ja": "ja", "ko": "ko"}


class DeepLTranslator:
    def __init__(
        self,
        settings: TranslateSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        blocked = _precheck(self._settings, request, provider="deepl")
        if blocked is not None:
            return blocked
        payload: dict[str, Any] = {
            "text": [request.text],
            "target_lang": _mapped_lang(_DEEPL_LANG, request.target_lang),
        }
        if request.source_lang != "auto":
            payload["source_lang"] = _mapped_lang(_DEEPL_LANG, request.source_lang)
        if payload["target_lang"] is None or (
            request.source_lang != "auto" and payload.get("source_lang") is None
        ):
            return _failure(self._settings, request, "deepl", "unsupported_language")
        body, error = _post_json(
            self._client,
            _join_url(self._settings.base_url or _DEEPL_DEFAULT, "/v2/translate"),
            headers={
                "Authorization": f"DeepL-Auth-Key {self._settings.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json_body=payload,
            timeout_seconds=self._settings.timeout_seconds,
        )
        if error or body is None:
            return _failure(self._settings, request, "deepl", error or "empty_response")
        translations = body.get("translations")
        if not isinstance(translations, list) or not translations:
            return _failure(self._settings, request, "deepl", "empty_translation")
        first = translations[0]
        text = first.get("text") if isinstance(first, dict) else None
        if not isinstance(text, str) or not text.strip():
            return _failure(self._settings, request, "deepl", "empty_translation")
        return _success(self._settings, request, "deepl", text.strip())


class MicrosoftTranslator:
    def __init__(
        self,
        settings: TranslateSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        blocked = _precheck(self._settings, request, provider="microsoft")
        if blocked is not None:
            return blocked
        target = _mapped_lang(_MICROSOFT_LANG, request.target_lang)
        if target is None:
            return _failure(self._settings, request, "microsoft", "unsupported_language")
        params = {"api-version": "3.0", "to": target}
        if request.source_lang != "auto":
            source = _mapped_lang(_MICROSOFT_LANG, request.source_lang)
            if source is None:
                return _failure(
                    self._settings,
                    request,
                    "microsoft",
                    "unsupported_language",
                )
            params["from"] = source
        url = _join_url(self._settings.base_url or _MICROSOFT_DEFAULT, "/translate")
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"
        body, error = _post_json(
            self._client,
            url,
            headers={
                "Ocp-Apim-Subscription-Key": self._settings.api_key.get_secret_value(),
                "Ocp-Apim-Subscription-Region": self._settings.region,
                "Content-Type": "application/json",
            },
            json_body=[{"Text": request.text}],
            timeout_seconds=self._settings.timeout_seconds,
        )
        if error or body is None:
            return _failure(
                self._settings,
                request,
                "microsoft",
                error or "empty_response",
            )
        if not isinstance(body, list) or not body:
            return _failure(self._settings, request, "microsoft", "empty_translation")
        first = body[0]
        translations = first.get("translations") if isinstance(first, dict) else None
        if not isinstance(translations, list) or not translations:
            return _failure(self._settings, request, "microsoft", "empty_translation")
        text = translations[0].get("text") if isinstance(translations[0], dict) else None
        if not isinstance(text, str) or not text.strip():
            return _failure(self._settings, request, "microsoft", "empty_translation")
        return _success(self._settings, request, "microsoft", text.strip())


class GoogleTranslator:
    def __init__(
        self,
        settings: TranslateSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        blocked = _precheck(self._settings, request, provider="google")
        if blocked is not None:
            return blocked
        target = _mapped_lang(_GOOGLE_LANG, request.target_lang)
        if target is None:
            return _failure(self._settings, request, "google", "unsupported_language")
        payload: dict[str, Any] = {
            "q": request.text,
            "target": target,
            "format": "text",
        }
        if request.source_lang != "auto":
            source = _mapped_lang(_GOOGLE_LANG, request.source_lang)
            if source is None:
                return _failure(self._settings, request, "google", "unsupported_language")
            payload["source"] = source
        url = self._settings.base_url or _GOOGLE_DEFAULT
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode({'key': self._settings.api_key.get_secret_value()})}"
        body, error = _post_json(
            self._client,
            url,
            headers={"Content-Type": "application/json"},
            json_body=payload,
            timeout_seconds=self._settings.timeout_seconds,
        )
        if error or body is None:
            return _failure(self._settings, request, "google", error or "empty_response")
        data = body.get("data") if isinstance(body, dict) else None
        translations = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(translations, list) or not translations:
            return _failure(self._settings, request, "google", "empty_translation")
        raw = translations[0].get("translatedText") if isinstance(translations[0], dict) else None
        if not isinstance(raw, str) or not raw.strip():
            return _failure(self._settings, request, "google", "empty_translation")
        return _success(self._settings, request, "google", html.unescape(raw).strip())


def _precheck(
    settings: TranslateSettings,
    request: TranslationRequest,
    *,
    provider: str,
) -> TranslationResult | None:
    if not settings.ready:
        return _failure(settings, request, provider, "translate_not_configured")
    if len(request.text) > _MAX_TEXT_CHARS:
        return _failure(settings, request, provider, "text_too_long")
    return None


def _mapped_lang(table: dict[str, str], value: str) -> str | None:
    return table.get(value.strip().lower())


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}{path}"


def _post_json(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    json_body: object,
    timeout_seconds: float,
) -> tuple[Any | None, str | None]:
    try:
        response = client.post(
            url,
            headers=headers,
            json=json_body,
            timeout=timeout_seconds,
        )
    except httpx.TimeoutException:
        return None, "timeout"
    except httpx.HTTPError:
        return None, "http_error"
    try:
        body = response.json()
    except ValueError:
        return None, "invalid_json"
    if response.status_code >= 400:
        return body, f"http_{response.status_code}"
    return body, None


def _failure(
    settings: TranslateSettings,
    request: TranslationRequest,
    provider: str,
    error: str,
) -> TranslationResult:
    return TranslationResult(
        status=JobStatus.FAILURE,
        source_text=request.text,
        translated_text=None,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
        model=provider,
        error=error,
    )


def _success(
    settings: TranslateSettings,
    request: TranslationRequest,
    provider: str,
    text: str,
) -> TranslationResult:
    return TranslationResult(
        status=JobStatus.SUCCESS,
        source_text=request.text,
        translated_text=text,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
        model=provider,
    )
