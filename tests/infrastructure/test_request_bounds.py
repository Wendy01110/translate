import gzip

import httpx
import pytest

from ai_translate.config import OcrSettings, StandardOcrSettings, TranslateSettings
from ai_translate.core.models import JobStatus, TranslationRequest
from ai_translate.infrastructure.http_response import MAX_RESPONSE_BYTES, read_bounded_response
from ai_translate.infrastructure.ocr_client import HttpOcrEngine
from ai_translate.infrastructure.ocr_space import OcrSpaceEngine
from ai_translate.infrastructure.official_translate import (
    DeepLTranslator,
    GoogleTranslator,
    MicrosoftTranslator,
)
from ai_translate.infrastructure.translate_client import HttpTranslator
from ai_translate.infrastructure.web_translate import (
    BingWebTranslator,
    DeepLWebTranslator,
    GoogleWebTranslator,
)

TRANSLATORS = {
    "openai": HttpTranslator,
    "deepl": DeepLTranslator,
    "microsoft": MicrosoftTranslator,
    "google": GoogleTranslator,
    "google_web": GoogleWebTranslator,
    "bing_web": BingWebTranslator,
    "deepl_web": DeepLWebTranslator,
}
CLIENT_KINDS = [*TRANSLATORS, "ocr_model", "ocr_standard"]


class TrackingStream(httpx.SyncByteStream):
    def __init__(self, chunks) -> None:
        self._chunks = chunks
        self.reads = 0
        self.closed = False

    def __iter__(self):
        for chunk in self._chunks:
            self.reads += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


def _call(client: httpx.Client, kind: str, text: str = "Synthetic input"):
    if kind == "ocr_model":
        return HttpOcrEngine(
            OcrSettings.model_construct(base_url="https://example.test/v1", model="fake", engine="model"),
            client=client,
        ).recognize(b"synthetic", "image/png")
    if kind == "ocr_standard":
        return OcrSpaceEngine(
            StandardOcrSettings(_env_file=None, api_key="test-key"), client=client,
        ).recognize(b"synthetic", "image/png")
    return TRANSLATORS[kind](
        TranslateSettings(
            _env_file=None,
            provider=kind,
            base_url="https://example.test/v1",
            api_key="test-key",
            region="test-region",
            model="fake",
        ),
        client=client,
    ).translate(TranslationRequest(text, "auto", "zh"))


@pytest.mark.parametrize("kind", list(TRANSLATORS))
@pytest.mark.parametrize("length", [8000, 8001])
def test_all_translators_enforce_the_input_boundary(kind: str, length: int) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(502, text="Synthetic upstream error")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _call(client, kind, "x" * length)
    assert result.error == ("http_502" if length == 8000 else "text_too_long")
    assert len(calls) == (1 if length == 8000 else 0)


def test_google_web_reports_encoded_url_limit_without_sending_http() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("Oversized URL must not reach HTTP")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _call(client, "google_web", "字" * 8000)
    assert result.error == "request_url_too_long"
    assert result.translated_text is None


@pytest.mark.parametrize("kind", CLIENT_KINDS)
def test_oversized_response_stops_reading_and_closes_stream(kind: str) -> None:
    stream = TrackingStream(b"x" * (64 * 1024) for _ in range(100))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Length": "1"}, stream=stream)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _call(client, kind)
    assert result.status is JobStatus.FAILURE
    assert result.error == (
        "ocr_response_too_large" if kind == "ocr_standard" else "response_too_large"
    )
    assert stream.reads <= 32
    assert stream.closed is True


@pytest.mark.parametrize("kind", CLIENT_KINDS)
def test_http_errors_close_stream_without_reading_or_exposing_body(kind: str) -> None:
    stream = TrackingStream([b"Synthetic upstream detail"])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, stream=stream)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _call(client, kind)
    assert result.error == "http_503"
    assert stream.reads == 0
    assert stream.closed is True


@pytest.mark.parametrize("kind", CLIENT_KINDS)
def test_deeply_nested_json_returns_failure_and_closes_stream(kind: str) -> None:
    content = b'{"nested":' + b"[" * 10_000 + b"0" + b"]" * 10_000 + b"}"
    stream = TrackingStream([content])
    with httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, stream=stream)
    )) as client:
        result = _call(client, kind)
    assert result.status is JobStatus.FAILURE
    assert result.error == "invalid_json"
    assert stream.closed is True


@pytest.mark.parametrize("body", [[], ["synthetic"], "synthetic", 17, True])
def test_deepl_non_object_response_returns_failure(body: object) -> None:
    with httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json=body)
    )) as client:
        result = _call(client, "deepl")
    assert result.status is JobStatus.FAILURE
    assert result.error == "empty_translation"
    assert result.translated_text is None


def test_gzip_response_limit_counts_decoded_bytes() -> None:
    compressed = gzip.compress(b"x" * (MAX_RESPONSE_BYTES + 1))
    stream = TrackingStream([compressed])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, stream=stream,
            headers={"Content-Encoding": "gzip", "Content-Length": str(len(compressed))},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _call(client, "openai")
    assert result.error == "response_too_large"
    assert stream.closed is True


def test_response_at_exact_limit_is_accepted() -> None:
    stream = TrackingStream([b"x" * MAX_RESPONSE_BYTES])
    with httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, stream=stream)
    )) as client:
        with client.stream("GET", "https://example.test") as response:
            content = read_bounded_response(response)
    assert len(content) == MAX_RESPONSE_BYTES
    assert stream.closed is True
