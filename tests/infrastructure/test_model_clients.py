from __future__ import annotations

import json

import httpx
import pytest

from ai_translate.config import OcrSettings, TranslateSettings
from ai_translate.core.models import JobStatus, TranslationRequest
from ai_translate.infrastructure.ocr_client import HttpOcrEngine
from ai_translate.infrastructure.translate_client import HttpTranslator


def test_translator_uses_only_translate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://translate.example/v1")
    monkeypatch.setenv("TRANSLATE_MODEL", "translate-model")
    monkeypatch.setenv("TRANSLATE_API_KEY", "translate-secret")
    monkeypatch.delenv("OCR_BASE_URL", raising=False)
    monkeypatch.delenv("OCR_MODEL", raising=False)

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  你好  "}}]},
        )

    translator = HttpTranslator(
        TranslateSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = translator.translate(
        TranslationRequest(text="Hello", source_lang="en", target_lang="zh")
    )

    assert result.status is JobStatus.SUCCESS
    assert result.translated_text == "你好"
    assert captured["url"] == "https://translate.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer translate-secret"
    assert captured["body"]["model"] == "translate-model"


def test_ocr_engine_uses_only_ocr_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("OCR_MODEL", "ocr-model")
    monkeypatch.setenv("OCR_API_KEY", "ocr-secret")
    monkeypatch.delenv("TRANSLATE_BASE_URL", raising=False)
    monkeypatch.delenv("TRANSLATE_MODEL", raising=False)

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Hello"}}]},
        )

    engine = HttpOcrEngine(
        OcrSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize(b"png-bytes", "image/png")

    assert result.status is JobStatus.SUCCESS
    assert result.text == "Hello"
    assert result.image_mode == "gundam"
    assert captured["url"] == "https://ocr.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer ocr-secret"
    assert captured["body"]["model"] == "ocr-model"
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["max_tokens"] == 24000
    assert captured["body"]["skip_special_tokens"] is False
    assert captured["body"]["images_config"] == {"image_mode": "gundam"}
    assert "vllm_xargs" not in captured["body"]
    assert "custom_logit_processor" not in captured["body"]
    content = captured["body"]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "document parsing."}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "ocr-secret" not in str(captured["body"])


def test_unconfigured_translator_does_not_call_http() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    translator = HttpTranslator(
        TranslateSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = translator.translate(
        TranslationRequest(text="Hello", source_lang="auto", target_lang="zh")
    )
    assert result.status is JobStatus.FAILURE
    assert result.error == "translate_not_configured"


def test_translator_timeout_is_classified() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    settings = TranslateSettings(
        base_url="https://translate.example/v1",
        model="translate-model",
        _env_file=None,
    )
    translator = HttpTranslator(
        settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = translator.translate(
        TranslationRequest(text="Hello", source_lang="auto", target_lang="zh")
    )
    assert result.status is JobStatus.FAILURE
    assert result.error == "timeout"


def test_ocr_multi_page_uses_base_mode_and_multi_page_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("OCR_MODEL", "Unlimited-OCR")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "page one\npage two"}}]},
        )

    engine = HttpOcrEngine(
        OcrSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize_pages([(b"one", "image/png"), (b"two", "image/png")])

    assert result.status is JobStatus.SUCCESS
    assert result.image_mode == "base"
    assert captured["body"]["images_config"] == {"image_mode": "base"}
    assert captured["body"]["messages"][0]["content"][0]["text"] == "Multi page parsing."
    assert sum(
        1
        for item in captured["body"]["messages"][0]["content"]
        if item.get("type") == "image_url"
    ) == 2


def test_ocr_rejects_gundam_for_multiple_images_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("OCR_IMAGE_MODE", "gundam")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    engine = HttpOcrEngine(
        OcrSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize_pages([(b"one", "image/png"), (b"two", "image/png")])
    assert result.status is JobStatus.FAILURE
    assert result.error == "ocr_image_mode_unsupported"


def test_ocr_truncation_does_not_return_partial_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": "partial private page text"},
                    }
                ]
            },
        )

    engine = HttpOcrEngine(
        OcrSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize(b"png", "image/png")
    assert result.status is JobStatus.FAILURE
    assert result.error == "ocr_output_truncated"
    assert result.text is None
    assert result.raw_text is None


def test_ocr_strips_grounding_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "text [1,2,3,4]Hello<|ref|><|det|>[0,0,1,1]<|/det|><|/ref|>"
                        }
                    }
                ]
            },
        )

    engine = HttpOcrEngine(
        OcrSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize(b"png", "image/png")
    assert result.status is JobStatus.SUCCESS
    assert result.text == "Hello"
    assert result.raw_text is not None
    assert "<|det|>" in result.raw_text


def test_default_clients_disable_env_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_BASE_URL", "https://ocr.example/v1")
    monkeypatch.setenv("TRANSLATE_BASE_URL", "https://translate.example/v1")
    monkeypatch.setenv("TRANSLATE_MODEL", "translate-model")
    engine = HttpOcrEngine(OcrSettings(_env_file=None))
    translator = HttpTranslator(TranslateSettings(_env_file=None))
    assert engine._client.trust_env is False
    assert translator._client.trust_env is False
