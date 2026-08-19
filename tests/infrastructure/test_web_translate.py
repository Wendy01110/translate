from __future__ import annotations

import httpx

from ai_translate.config import TranslateSettings
from ai_translate.core.models import JobStatus, TranslationRequest
from ai_translate.infrastructure.web_translate import (
    BingWebTranslator,
    DeepLWebTranslator,
    GoogleWebTranslator,
    parse_bing_page,
)


def _settings(provider: str, monkeypatch) -> TranslateSettings:
    monkeypatch.setenv("TRANSLATE_PROVIDER", provider)
    monkeypatch.delenv("TRANSLATE_API_KEY", raising=False)
    monkeypatch.delenv("TRANSLATE_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSLATE_MODEL", raising=False)
    return TranslateSettings(_env_file=None)


def test_google_web_uses_gtx_client(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=[[["你好", "Hello", None, None, 10]]])

    result = GoogleWebTranslator(
        _settings("google_web", monkeypatch),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).translate(TranslationRequest(text="Hello", source_lang="auto", target_lang="zh"))
    assert result.status is JobStatus.SUCCESS
    assert result.translated_text == "你好"
    assert result.model == "google_web"
    assert "client=gtx" in str(captured["url"])
    assert "dt=t" in str(captured["url"])
    assert "translate.google.com/translate_a/single" in str(captured["url"])


def test_parse_bing_page_reads_helper_and_ig() -> None:
    html = (
        'var IG:"ABC123"; params_AbusePreventionHelper = [1,"tok",3600000];'
    )
    parsed = parse_bing_page(html)
    assert parsed == {"key": "1", "token": "tok", "ig": "ABC123"}


def test_bing_web_uses_translator_page_then_ttranslatev3(monkeypatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "ttranslatev3" in str(request.url):
            form = request.content.decode()
            assert "fromLang=auto-detect" in form
            assert "to=zh-Hans" in form
            return httpx.Response(
                200,
                json=[{"translations": [{"text": "你好", "to": "zh-Hans"}]}],
            )
        return httpx.Response(
            200,
            text='IG:"ABC123"; params_AbusePreventionHelper = [1,"tok",3600000];',
        )

    result = BingWebTranslator(
        _settings("bing_web", monkeypatch),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).translate(TranslationRequest(text="Hello", source_lang="auto", target_lang="zh"))
    assert result.status is JobStatus.SUCCESS
    assert result.translated_text == "你好"
    assert any("bing.com/translator" in url for url in calls)
    assert any("ttranslatev3" in url for url in calls)


def test_deepl_web_posts_jsonrpc(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={"result": {"texts": [{"text": "你好"}]}},
        )

    result = DeepLWebTranslator(
        _settings("deepl_web", monkeypatch),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    ).translate(TranslationRequest(text="Hello", source_lang="auto", target_lang="zh"))
    assert result.status is JobStatus.SUCCESS
    assert result.translated_text == "你好"
    assert captured["url"] == "https://www2.deepl.com/jsonrpc"
    assert "LMT_handle_texts" in str(captured["body"])


def test_google_web_is_ready_without_key(monkeypatch) -> None:
    settings = _settings("google_web", monkeypatch)
    assert settings.ready is True
    assert not settings.api_key_set
