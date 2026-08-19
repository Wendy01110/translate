from ai_translate.core.models import JobStatus
from ai_translate.infrastructure.ocr_routing import RoutingOcrEngine
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
