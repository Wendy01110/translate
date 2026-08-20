from __future__ import annotations

import httpx

from ai_translate.config import StandardOcrSettings
from ai_translate.core.models import JobStatus
from ai_translate.infrastructure.ocr_space import (
    OCR_SPACE_MAX_IMAGE_BYTES,
    OCR_SPACE_MAX_RESPONSE_BYTES,
    OcrSpaceEngine,
)


def test_ocr_space_posts_bounded_base64_form_and_parses_text() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("apikey")
        captured["content_type"] = request.headers.get("Content-Type")
        captured["body"] = request.content
        return httpx.Response(
            200,
            json={
                "OCRExitCode": 1,
                "IsErroredOnProcessing": False,
                "ParsedResults": [
                    {"FileParseExitCode": 1, "ParsedText": "  Hello 世界  "}
                ],
            },
        )

    settings = StandardOcrSettings(api_key="standard-secret", _env_file=None)
    engine = OcrSpaceEngine(
        settings,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize(b"png-bytes", "image/png")

    assert result.status is JobStatus.SUCCESS
    assert result.text == "Hello 世界"
    assert result.engine == "standard"
    assert result.model == "ocr.space-engine-2"
    assert captured["url"] == "https://api.ocr.space/parse/image"
    assert captured["api_key"] == "standard-secret"
    assert str(captured["content_type"]).startswith("multipart/form-data;")
    body = bytes(captured["body"])
    assert b'name="base64Image"' in body
    assert b"data:image/png;base64," in body
    assert b'name="OCREngine"' in body
    assert b"standard-secret" not in body


def test_unconfigured_ocr_space_does_not_call_http() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    engine = OcrSpaceEngine(
        StandardOcrSettings(_env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize(b"png", "image/png")
    assert result.status is JobStatus.FAILURE
    assert result.error == "ocr_standard_not_configured"


def test_ocr_space_rejects_multi_page_and_oversize_without_http() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    engine = OcrSpaceEngine(
        StandardOcrSettings(api_key="standard-secret", _env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    multi = engine.recognize_pages([(b"one", "image/png"), (b"two", "image/png")])
    large = engine.recognize(
        b"x" * (OCR_SPACE_MAX_IMAGE_BYTES + 1),
        "image/png",
    )
    assert multi.error == "ocr_standard_multi_page_unsupported"
    assert large.error == "ocr_standard_image_too_large"


def test_ocr_space_does_not_expose_upstream_error_details() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "OCRExitCode": 3,
                "IsErroredOnProcessing": True,
                "ErrorMessage": "private upstream detail",
                "ParsedResults": [],
            },
        )

    engine = OcrSpaceEngine(
        StandardOcrSettings(api_key="standard-secret", _env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize(b"png", "image/png")
    assert result.error == "empty_ocr_text"
    assert "private" not in repr(result)


def test_ocr_space_rejects_oversized_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (OCR_SPACE_MAX_RESPONSE_BYTES + 1))

    engine = OcrSpaceEngine(
        StandardOcrSettings(api_key="standard-secret", _env_file=None),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = engine.recognize(b"png", "image/png")
    assert result.error == "ocr_response_too_large"


def test_default_ocr_space_client_disables_env_proxy() -> None:
    engine = OcrSpaceEngine(
        StandardOcrSettings(api_key="standard-secret", _env_file=None)
    )
    assert engine._client.trust_env is False
