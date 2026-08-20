from ai_translate.core.models import JobStatus
from ai_translate.infrastructure.ocr_routing import (
    RoutingOcrEngine,
    TieredLocalOcrEngine,
    TieredRemoteOcrEngine,
)
from ai_translate.infrastructure.ocr_space import OCR_SPACE_MAX_IMAGE_BYTES
from tests.support import FakeOcrEngine


def test_auto_uses_local_when_confident() -> None:
    remote = FakeOcrEngine(text="from-model", model="Unlimited-OCR")
    local = _ResultOcr("Hello", engine="vision", confidence=0.9)
    engine = RoutingOcrEngine(local=local, remote=remote, mode="auto", min_confidence=0.5)
    result = engine.recognize(b"png", "image/png")
    assert result.text == "Hello"
    assert result.engine == "vision"
    assert remote.calls == []


def test_auto_falls_back_to_model_when_local_is_empty() -> None:
    local = _ResultOcr("", status=JobStatus.FAILURE, error="empty_ocr_text", engine="vision")
    remote = FakeOcrEngine(text="from-model", model="Unlimited-OCR")
    engine = RoutingOcrEngine(local=local, remote=remote, mode="auto", min_confidence=0.5)
    result = engine.recognize(b"png", "image/png")
    assert result.text == "from-model"
    assert remote.calls


def test_auto_falls_back_when_confidence_is_low() -> None:
    local = _ResultOcr("x", engine="vision", confidence=0.1)
    remote = FakeOcrEngine(text="from-model")
    engine = RoutingOcrEngine(local=local, remote=remote, mode="auto", min_confidence=0.5)
    result = engine.recognize(b"png", "image/png")
    assert result.text == "from-model"


def test_vision_mode_does_not_call_model() -> None:
    local = _ResultOcr("", status=JobStatus.FAILURE, error="empty_ocr_text", engine="vision")
    remote = FakeOcrEngine(text="from-model")
    engine = RoutingOcrEngine(local=local, remote=remote, mode="vision", min_confidence=0.5)
    result = engine.recognize(b"png", "image/png")
    assert result.error == "empty_ocr_text"
    assert remote.calls == []


def test_model_mode_skips_local() -> None:
    local = _ResultOcr("Hello", engine="vision", confidence=0.9)
    remote = FakeOcrEngine(text="from-model")
    engine = RoutingOcrEngine(local=local, remote=remote, mode="model", min_confidence=0.5)
    result = engine.recognize(b"png", "image/png")
    assert result.text == "from-model"
    assert local.calls == []


def test_standard_mode_skips_local_and_uses_selected_remote() -> None:
    local = _ResultOcr("Hello", engine="vision", confidence=0.9)
    standard = FakeOcrEngine(text="from-standard", model="ocr.space-engine-2")
    engine = RoutingOcrEngine(
        local=local,
        remote=standard,
        mode="standard",
        min_confidence=0.5,
    )
    result = engine.recognize(b"png", "image/png")
    assert result.text == "from-standard"
    assert local.calls == []


def test_auto_uses_local_advanced_before_remote_api() -> None:
    vision = _ResultOcr(
        "",
        status=JobStatus.FAILURE,
        error="empty_ocr_text",
        engine="vision",
    )
    paddle = _ResultOcr("from-paddle", engine="paddle", confidence=0.9)
    local = TieredLocalOcrEngine(
        standard=vision,
        advanced=paddle,
        min_confidence=0.5,
    )
    remote = FakeOcrEngine(text="from-api")
    engine = RoutingOcrEngine(
        local=local,
        remote=remote,
        mode="auto",
        min_confidence=0.5,
    )

    result = engine.recognize(b"png", "image/png")

    assert result.text == "from-paddle"
    assert vision.calls
    assert paddle.calls
    assert remote.calls == []


def test_auto_reaches_api_after_both_local_tiers_fail() -> None:
    vision = _ResultOcr(
        "",
        status=JobStatus.FAILURE,
        error="empty_ocr_text",
        engine="vision",
    )
    paddle = _ResultOcr(
        "",
        status=JobStatus.FAILURE,
        error="empty_ocr_text",
        engine="paddle",
    )
    local = TieredLocalOcrEngine(
        standard=vision,
        advanced=paddle,
        min_confidence=0.5,
    )
    remote = FakeOcrEngine(text="from-api")
    engine = RoutingOcrEngine(
        local=local,
        remote=remote,
        mode="auto",
        min_confidence=0.5,
    )

    result = engine.recognize(b"png", "image/png")

    assert result.text == "from-api"
    assert vision.calls
    assert paddle.calls
    assert remote.calls


def test_paddle_mode_does_not_call_remote() -> None:
    paddle = _ResultOcr("from-paddle", engine="paddle", confidence=0.9)
    remote = FakeOcrEngine(text="from-api")
    engine = RoutingOcrEngine(
        local=paddle,
        remote=remote,
        mode="paddle",
        min_confidence=0.5,
    )

    result = engine.recognize(b"png", "image/png")

    assert result.text == "from-paddle"
    assert paddle.calls
    assert remote.calls == []


def test_tiered_remote_stops_after_standard_success() -> None:
    standard = FakeOcrEngine(text="from-standard")
    advanced = FakeOcrEngine(text="from-advanced")
    engine = TieredRemoteOcrEngine(standard=standard, advanced=advanced)
    result = engine.recognize(b"png", "image/png")
    assert result.text == "from-standard"
    assert standard.calls
    assert advanced.calls == []


def test_tiered_remote_falls_back_after_standard_failure() -> None:
    standard = FakeOcrEngine(
        text=None,
        status=JobStatus.FAILURE,
        error="empty_ocr_text",
    )
    advanced = FakeOcrEngine(text="from-advanced")
    engine = TieredRemoteOcrEngine(standard=standard, advanced=advanced)
    result = engine.recognize(b"png", "image/png")
    assert result.text == "from-advanced"
    assert standard.calls
    assert advanced.calls


def test_tiered_remote_sends_large_or_multi_page_directly_to_advanced() -> None:
    standard = FakeOcrEngine(text="must-not-run")
    advanced = FakeOcrEngine(text="from-advanced")
    engine = TieredRemoteOcrEngine(standard=standard, advanced=advanced)
    large = engine.recognize(
        b"x" * (OCR_SPACE_MAX_IMAGE_BYTES + 1),
        "image/png",
    )
    multi = engine.recognize_pages(
        [(b"one", "image/png"), (b"two", "image/png")]
    )
    assert large.text == "from-advanced"
    assert multi.text == "from-advanced"
    assert standard.calls == []
    assert len(advanced.calls) == 2


class _ResultOcr:
    def __init__(
        self,
        text: str,
        *,
        status: JobStatus = JobStatus.SUCCESS,
        error: str | None = None,
        engine: str = "vision",
        confidence: float | None = None,
    ) -> None:
        from ai_translate.core.models import OcrResult

        self.calls: list[object] = []
        self._result = OcrResult(
            status=status,
            text=text or None,
            model="macos-vision",
            error=error,
            engine=engine,
            confidence=confidence,
        )

    def recognize(self, image_bytes: bytes, mime_type: str):
        return self.recognize_pages([(image_bytes, mime_type)])

    def recognize_pages(self, pages):
        self.calls.append(list(pages))
        return self._result
