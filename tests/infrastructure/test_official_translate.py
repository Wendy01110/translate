from __future__ import annotations

import json

import httpx

from ai_translate.config import TranslateSettings
from ai_translate.core.models import JobStatus, TranslationRequest
from ai_translate.infrastructure.official_translate import (
    DeepLTranslator,
    GoogleTranslator,
    MicrosoftTranslator,
)


def _settings(**env: str) -> TranslateSettings:
    return TranslateSettings(_env_file=None, **env)


def test_deepl_uses_official_v2_contract() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"translations": [{"text": "你好", "detected_source_language": "EN"}]},
        )

    result = DeepLTranslator(
        _settings(provider="deepl", api_key="deepl-test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).translate(TranslationRequest(text="Hello", source_lang="auto", target_lang="zh"))
    assert result.status is JobStatus.SUCCESS
    assert result.translated_text == "你好"
    assert result.model == "deepl"
    assert captured["url"] == "https://api-free.deepl.com/v2/translate"
    assert captured["authorization"] == "DeepL-Auth-Key deepl-test-key"
    assert captured["body"]["target_lang"] == "ZH"
    assert "source_lang" not in captured["body"]


def test_microsoft_uses_official_v3_contract() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("Ocp-Apim-Subscription-Key")
        captured["region"] = request.headers.get("Ocp-Apim-Subscription-Region")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=[{"translations": [{"text": "你好", "to": "zh-Hans"}]}],
        )

    result = MicrosoftTranslator(
        _settings(provider="microsoft", api_key="ms-test-key", region="eastus"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).translate(TranslationRequest(text="Hello", source_lang="en", target_lang="zh"))
    assert result.status is JobStatus.SUCCESS
    assert result.translated_text == "你好"
    assert "api-version=3.0" in str(captured["url"])
    assert "to=zh-Hans" in str(captured["url"])
    assert captured["key"] == "ms-test-key"
    assert captured["region"] == "eastus"
    assert captured["body"] == [{"Text": "Hello"}]


def test_google_uses_official_v2_contract() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"data": {"translations": [{"translatedText": "你好"}]}},
        )

    result = GoogleTranslator(
        _settings(provider="google", api_key="google-test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).translate(TranslationRequest(text="Hello", source_lang="auto", target_lang="zh"))
    assert result.status is JobStatus.SUCCESS
    assert result.translated_text == "你好"
    assert "language/translate/v2" in str(captured["url"])
    assert "key=google-test-key" in str(captured["url"])
    assert captured["body"]["target"] == "zh-CN"
    assert "source" not in captured["body"]


def test_official_translator_skips_request_when_not_configured() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    result = DeepLTranslator(
        _settings(provider="deepl", api_key=""),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).translate(TranslationRequest(text="Hello", source_lang="en", target_lang="zh"))
    assert result.status is JobStatus.FAILURE
    assert result.error == "translate_not_configured"
    assert calls["n"] == 0
