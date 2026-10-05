import base64
import json
from collections.abc import Sequence

import httpx
import pytest

from ai_translate.config import LocalAdvancedOcrSettings, OcrSettings, StandardOcrSettings
from ai_translate.core.limits import MAX_IMAGE_BYTES
from ai_translate.core.models import JobStatus, OcrResult
from ai_translate.core.ports import OcrEngine
from ai_translate.infrastructure.ocr_client import HttpOcrEngine
from ai_translate.infrastructure.ocr_routing import (
    RoutingOcrEngine,
    TieredLocalOcrEngine,
    TieredRemoteOcrEngine,
)
from ai_translate.infrastructure.ocr_space import OcrSpaceEngine
from ai_translate.infrastructure.paddle_ocr import PaddleOcrEngine
from ai_translate.infrastructure.vision_ocr import VisionOcrEngine


class _TrackedOcr:
    def __init__(self, name: str, events: list[str]) -> None:
        self._name = name
        self._events = events

    def recognize(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages: Sequence[tuple[bytes, str]]) -> OcrResult:
        self._events.append(self._name)
        return OcrResult(JobStatus.SUCCESS, "Hello", "fake-ocr", confidence=1.0)


def _engine(kind: str, events: list[str]) -> OcrEngine:
    def http(_request: httpx.Request) -> httpx.Response:
        events.append("http")
        if kind == "standard":
            return httpx.Response(
                200,
                json={"OCRExitCode": 1, "ParsedResults": [{"ParsedText": "Hello"}]},
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello"}}]})

    if kind == "model":
        return HttpOcrEngine(
            OcrSettings(
                base_url="https://ocr.example.invalid/v1", model="vision-model",
                api_key="", image_mode="base", _env_file=None,
            ),
            client=httpx.Client(transport=httpx.MockTransport(http)),
        )
    if kind == "standard":
        return OcrSpaceEngine(
            StandardOcrSettings(api_key="synthetic-key", _env_file=None),
            client=httpx.Client(transport=httpx.MockTransport(http)),
        )
    if kind == "vision":
        def recognize(_data: bytes, _mime: str) -> tuple[str, float]:
            events.append("vision")
            return "Hello", 1.0

        return VisionOcrEngine(recognize=recognize)
    if kind == "paddle":
        class Pipeline:
            def predict(self, _image: object) -> list[dict[str, object]]:
                events.append("predict")
                return [{"rec_texts": ["Hello"], "rec_scores": [1.0]}]

        def factory(**_options: object) -> Pipeline:
            events.append("init")
            return Pipeline()

        def decode(data: bytes) -> bytes:
            events.append("decode")
            return data

        return PaddleOcrEngine(
            LocalAdvancedOcrSettings(_env_file=None),
            factory=factory, decoder=decode,
            on_first_load=lambda _model: events.append("notify"),
        )
    if kind == "local_tiers":
        return TieredLocalOcrEngine(
            standard=_TrackedOcr("local-standard", events),
            advanced=_TrackedOcr("local-advanced", events), min_confidence=0.5,
        )
    if kind == "remote_tiers":
        return TieredRemoteOcrEngine(
            standard=_TrackedOcr("api-standard", events),
            advanced=_TrackedOcr("api-advanced", events),
        )
    return RoutingOcrEngine(
        local=_TrackedOcr("local", events), remote=_TrackedOcr("remote", events),
        mode=kind.removesuffix("_mode"), min_confidence=0.5,
    )


@pytest.fixture(scope="module")
def invalid_inputs() -> dict[str, tuple[list[tuple[bytes, str]], str]]:
    half = b"x" * (MAX_IMAGE_BYTES // 2 + 1)
    large = b"x" * (MAX_IMAGE_BYTES + 1)
    return {
        "count": ([(b"x", "image/png")] * 11, "ocr_too_many_pages"),
        "batch": ([(half, "image/png")] * 2, "ocr_batch_too_large"),
        "single": ([(large, "image/png")], "image_too_large"),
    }


@pytest.mark.parametrize(
    "kind",
    [
        "vision", "paddle", "model", "standard", "local_tiers", "remote_tiers",
        "auto", "vision_mode", "paddle_mode", "standard_mode", "model_mode",
    ],
)
@pytest.mark.parametrize("budget", ["count", "batch", "single"])
def test_ocr_input_budget_stops_all_processing(
    monkeypatch: pytest.MonkeyPatch,
    invalid_inputs: dict[str, tuple[list[tuple[bytes, str]], str]],
    kind: str,
    budget: str,
) -> None:
    events: list[str] = []

    def encode(_data: bytes) -> bytes:
        events.append("encode")
        return b"eA=="

    monkeypatch.setattr(base64, "b64encode", encode)
    pages, error = invalid_inputs[budget]
    result = _engine(kind, events).recognize_pages(pages)

    assert result.status is JobStatus.FAILURE
    assert result.error == error
    assert result.text is None
    assert result.raw_text is None
    assert events == []


@pytest.mark.parametrize("kind", ["auto", "local_tiers", "remote_tiers"])
@pytest.mark.parametrize("pages", [[], [(b"x", "image/png"), (b"", "image/png")]])
def test_empty_input_does_not_fall_through_ocr_tiers(
    kind: str, pages: list[tuple[bytes, str]],
) -> None:
    events: list[str] = []
    result = _engine(kind, events).recognize_pages(pages)
    assert result.error == "empty_image"
    assert events == []


@pytest.mark.parametrize("budget", ["count", "batch", "single"])
def test_exact_ocr_budget_is_accepted(
    invalid_inputs: dict[str, tuple[list[tuple[bytes, str]], str]], budget: str,
) -> None:
    if budget == "count":
        pages = [(b"x", "image/png")] * 10
    else:
        oversized, _error = invalid_inputs[budget]
        data = oversized[0][0][:-1]
        pages = [(data, "image/png")] * len(oversized)
        assert sum(len(data) for data, _mime in pages) == MAX_IMAGE_BYTES
    events: list[str] = []
    result = _engine("auto", events).recognize_pages(pages)
    assert result.status is JobStatus.SUCCESS
    assert events == ["local"]


def test_excess_page_count_does_not_inspect_page_data() -> None:
    class UnreadPages(Sequence[tuple[bytes, str]]):
        def __len__(self) -> int:
            return 11

        def __getitem__(self, _index):
            pytest.fail("Excess pages must be rejected before inspecting image data")

    events: list[str] = []
    result = _engine("auto", events).recognize_pages(UnreadPages())
    assert result.error == "ocr_too_many_pages"
    assert events == []


def test_ten_page_http_request_preserves_page_order() -> None:
    observed: list[bytes] = []

    def http(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        for item in body["messages"][0]["content"]:
            if item["type"] == "image_url":
                encoded = item["image_url"]["url"].split(",", 1)[1]
                observed.append(base64.b64decode(encoded))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello"}}]})

    engine = HttpOcrEngine(
        OcrSettings(
            base_url="https://ocr.example.invalid/v1", model="vision-model",
            api_key="", image_mode="base", _env_file=None,
        ),
        client=httpx.Client(transport=httpx.MockTransport(http)),
    )
    pages = [(bytes([index]), "image/png") for index in range(10)]
    result = engine.recognize_pages(pages)
    assert result.status is JobStatus.SUCCESS
    assert observed == [data for data, _mime in pages]


def test_vision_valid_pages_preserve_order() -> None:
    observed: list[bytes] = []

    def recognize(data: bytes, _mime: str) -> tuple[str, float]:
        observed.append(data)
        return data.decode(), 1.0

    result = VisionOcrEngine(recognize=recognize).recognize_pages(
        [(b"one", "image/png"), (b"two", "image/png")]
    )
    assert result.status is JobStatus.SUCCESS
    assert result.text == "one\ntwo"
    assert observed == [b"one", b"two"]
