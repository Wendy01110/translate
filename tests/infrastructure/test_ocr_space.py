from __future__ import annotations

import httpx
import pytest

from ai_translate.config import StandardOcrSettings
from ai_translate.core.models import JobStatus, OcrResult
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


@pytest.mark.parametrize("field", ["OCRExitCode", "FileParseExitCode"])
@pytest.mark.parametrize(
    "invalid_code",
    [[], {}, ["untrusted-detail"], {"detail": "untrusted-detail"}],
    ids=["empty-list", "empty-object", "list", "object"],
)
def test_ocr_space_rejects_structured_status_without_exposing_text(
    field: str, invalid_code: object
) -> None:
    item = {"FileParseExitCode": 1, "ParsedText": "untrusted-text"}
    payload = {
        "OCRExitCode": 1,
        "ParsedResults": [item],
        "ErrorMessage": "untrusted-detail",
    }
    if field == "OCRExitCode":
        payload[field] = invalid_code
    else:
        item[field] = invalid_code

    result = _recognize_response(httpx.Response(200, json=payload))

    assert result.status is JobStatus.FAILURE
    assert result.error == "empty_ocr_text"
    assert result.engine == "standard"
    assert result.text is None
    assert result.raw_text is None
    assert "untrusted" not in repr(result)


@pytest.mark.parametrize(
    ("exit_code", "file_code"),
    [(1, 1), (2, "1"), ("1", 1), ("2", "1"), (1, None)],
    ids=["integer", "partial-code", "string", "string-partial", "omitted-file-code"],
)
def test_ocr_space_keeps_supported_status_codes(
    exit_code: int | str, file_code: int | str | None
) -> None:
    item = {"ParsedText": "  Hello 世界  "}
    if file_code is not None:
        item["FileParseExitCode"] = file_code
    result = _recognize_response(
        httpx.Response(200, json={"OCRExitCode": exit_code, "ParsedResults": [item]})
    )

    assert result.status is JobStatus.SUCCESS
    assert result.text == "Hello 世界"
    assert result.error is None


@pytest.mark.parametrize("invalid_code", [[], {}], ids=["list", "object"])
def test_ocr_space_skips_invalid_entry_and_keeps_other_text_in_order(
    invalid_code: object,
) -> None:
    result = _recognize_response(
        httpx.Response(
            200,
            json={
                "OCRExitCode": 2,
                "ParsedResults": [
                    {"FileParseExitCode": 1, "ParsedText": " First "},
                    {"FileParseExitCode": invalid_code, "ParsedText": "untrusted-text"},
                    {"FileParseExitCode": "1", "ParsedText": " Second "},
                ],
            },
        )
    )

    assert result.status is JobStatus.SUCCESS
    assert result.text == "First\nSecond"
    assert result.raw_text == "First\nSecond"
    assert "untrusted" not in repr(result)


def test_ocr_space_maps_excessive_json_nesting_to_invalid_json() -> None:
    content = b'{"nested":' + b"[" * 10_000 + b"0" + b"]" * 10_000 + b"}"
    assert len(content) < OCR_SPACE_MAX_RESPONSE_BYTES

    result = _recognize_response(httpx.Response(200, content=content))

    assert result.status is JobStatus.FAILURE
    assert result.error == "invalid_json"
    assert result.text is None
    assert result.raw_text is None


def _recognize_response(response: httpx.Response) -> OcrResult:
    with httpx.Client(transport=httpx.MockTransport(lambda _request: response)) as client:
        engine = OcrSpaceEngine(
            StandardOcrSettings(api_key="standard-secret", _env_file=None),
            client=client,
        )
        return engine.recognize(b"png", "image/png")
