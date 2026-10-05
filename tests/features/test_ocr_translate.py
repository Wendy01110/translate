import pytest

from ai_translate.core.limits import MAX_IMAGE_BYTES
from ai_translate.core.models import JobKind, JobStatus, ScreenRect
from ai_translate.features.ocr_translate import (
    LIVE_SHOW,
    LIVE_SKIP_FRAME,
    LIVE_SKIP_TEXT,
    LIVE_STOPPED,
    LiveOcrAdvance,
    LiveOcrMemory,
    OcrTranslateService,
    image_signature,
)
from tests.support import FakeOcrEngine, FakeTranslator


def test_screen_rect_canonical_flips_negative_size() -> None:
    rect = ScreenRect(x=100, y=80, width=-40, height=-20).canonical()
    assert rect == ScreenRect(x=60, y=60, width=40, height=20)
    assert ScreenRect(x=0, y=0, width=8, height=8).is_usable() is False
    assert ScreenRect(x=0, y=0, width=16, height=16).is_usable() is True


def test_empty_image_fails_without_calling_ports() -> None:
    ocr = FakeOcrEngine()
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)

    job = service.translate_image(b"", "image/png", source_lang="auto", target_lang="zh")

    assert job.status is JobStatus.FAILURE
    assert job.error == "empty_image"
    assert ocr.calls == []
    assert translator.calls == []


@pytest.mark.parametrize(
    ("budget", "error"),
    [("count", "ocr_too_many_pages"), ("batch", "ocr_batch_too_large"), ("single", "image_too_large")],
)
def test_ocr_input_budget_fails_before_both_ports(budget: str, error: str) -> None:
    if budget == "count":
        pages = [(b"x", "image/png")] * 11
    elif budget == "batch":
        pages = [(b"x" * (MAX_IMAGE_BYTES // 2 + 1), "image/png")] * 2
    else:
        pages = [(b"x" * (MAX_IMAGE_BYTES + 1), "image/png")]
    ocr = FakeOcrEngine()
    translator = FakeTranslator()

    job = OcrTranslateService(ocr, translator).translate_pages(pages, "auto", "zh")

    assert job.status is JobStatus.FAILURE
    assert job.error == error
    assert job.source_text is None
    assert job.ocr_text is None
    assert job.translated_text is None
    assert ocr.calls == []
    assert translator.calls == []


def test_live_oversized_image_clears_previous_text_and_can_recover() -> None:
    ocr = FakeOcrEngine(text="New sentence")
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)
    result = service.advance_live(
        b"x" * (MAX_IMAGE_BYTES + 1), "image/png", "auto", "zh",
        frame_hash="large", memory=LiveOcrMemory(frame_hash="old", ocr_text="Old sentence"),
    )
    assert result.action == LIVE_SHOW
    assert result.job is not None
    assert result.job.status is JobStatus.FAILURE
    assert result.job.error == "image_too_large"
    assert result.job.translated_text is None
    assert result.memory.ocr_text == ""
    assert result.memory.retry_ocr is None
    assert ocr.calls == []
    assert translator.calls == []

    recovered = _advance(service, result.memory, frame="valid")
    assert recovered.job is not None
    assert recovered.job.status is JobStatus.SUCCESS
    assert len(ocr.calls) == 1
    assert len(translator.calls) == 1


def test_ocr_failure_does_not_call_translator() -> None:
    ocr = FakeOcrEngine(text=None, status=JobStatus.FAILURE, error="ocr_timeout")
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)

    job = service.translate_image(b"png", "image/png", source_lang="auto", target_lang="zh")

    assert job.kind is JobKind.OCR
    assert job.status is JobStatus.FAILURE
    assert job.error == "ocr_timeout"
    assert translator.calls == []


def test_empty_ocr_text_does_not_call_translator() -> None:
    ocr = FakeOcrEngine(text="   ", status=JobStatus.SUCCESS)
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)

    job = service.translate_image(b"png", "image/png", source_lang="auto", target_lang="zh")

    assert job.status is JobStatus.FAILURE
    assert job.error == "empty_ocr_text"
    assert translator.calls == []


def test_successful_ocr_translation() -> None:
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator(translated_text="你好")
    service = OcrTranslateService(ocr, translator)

    job = service.translate_image(b"png", "image/png", source_lang="auto", target_lang="zh")

    assert job.status is JobStatus.SUCCESS
    assert job.ocr_text == "Hello"
    assert job.source_text == "Hello"
    assert job.translated_text == "你好"
    assert translator.calls[0].text == "Hello"


def test_ocr_success_and_translate_failure_is_partial() -> None:
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator(
        translated_text=None,
        status=JobStatus.FAILURE,
        error="timeout",
    )
    service = OcrTranslateService(ocr, translator)

    job = service.translate_image(b"png", "image/png", source_lang="auto", target_lang="zh")

    assert job.status is JobStatus.PARTIAL
    assert job.ocr_text == "Hello"
    assert job.translated_text is None
    assert job.error == "timeout"


@pytest.mark.parametrize("live", [False, True])
def test_long_ocr_text_is_preserved_without_calling_translator(live: bool) -> None:
    source = "字" * 8001
    translator = FakeTranslator()
    service = OcrTranslateService(FakeOcrEngine(text=source), translator)
    if live:
        result = _advance(service)
        job = result.job
        assert _advance(service, result.memory).action == LIVE_SKIP_FRAME
    else:
        job = service.translate_image(b"synthetic", "image/png", "auto", "zh")
    assert job is not None
    assert job.status is JobStatus.PARTIAL
    assert job.error == "text_too_long"
    assert job.source_text == source
    assert job.ocr_text == source
    assert translator.calls == []


def test_live_skips_ocr_when_frame_hash_is_unchanged() -> None:
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)
    memory = LiveOcrMemory(frame_hash="same", ocr_text="Hello")

    result = service.advance_live(
        b"png",
        "image/png",
        "auto",
        "zh",
        frame_hash="same",
        memory=memory,
    )

    assert result.action == LIVE_SKIP_FRAME
    assert result.job is None
    assert ocr.calls == []
    assert translator.calls == []


def test_live_skips_translate_when_ocr_text_is_unchanged() -> None:
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)

    result = service.advance_live(
        b"png",
        "image/png",
        "auto",
        "zh",
        frame_hash="frame-2",
        memory=LiveOcrMemory(frame_hash="frame-1", ocr_text="Hello"),
    )

    assert result.action == LIVE_SKIP_TEXT
    assert result.memory.frame_hash == "frame-2"
    assert translator.calls == []
    assert len(ocr.calls) == 1


def test_live_translates_when_text_changes() -> None:
    ocr = FakeOcrEngine(text="World")
    translator = FakeTranslator(translated_text="世界")
    service = OcrTranslateService(ocr, translator)

    result = service.advance_live(
        b"png",
        "image/png",
        "auto",
        "zh",
        frame_hash="frame-2",
        memory=LiveOcrMemory(frame_hash="frame-1", ocr_text="Hello"),
    )

    assert result.action == LIVE_SHOW
    assert result.job is not None
    assert result.job.translated_text == "世界"
    assert translator.calls[0].text == "World"


def test_live_clears_when_ocr_is_empty() -> None:
    ocr = FakeOcrEngine(text="  ", status=JobStatus.SUCCESS)
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)

    result = service.advance_live(
        b"png",
        "image/png",
        "auto",
        "zh",
        frame_hash="frame-2",
        memory=LiveOcrMemory(frame_hash="frame-1", ocr_text="Hello"),
    )

    assert result.action == LIVE_SHOW
    assert result.job is not None
    assert result.job.status is JobStatus.FAILURE
    assert result.job.error == "empty_ocr_text"
    assert result.memory.ocr_text == ""
    assert translator.calls == []


def test_live_translate_failure_does_not_keep_previous_success() -> None:
    ocr = FakeOcrEngine(text="World")
    translator = FakeTranslator(
        translated_text=None,
        status=JobStatus.FAILURE,
        error="timeout",
    )
    service = OcrTranslateService(ocr, translator)

    result = service.advance_live(
        b"png",
        "image/png",
        "auto",
        "zh",
        frame_hash="frame-2",
        memory=LiveOcrMemory(frame_hash="frame-1", ocr_text="Hello"),
    )

    assert result.action == LIVE_SHOW
    assert result.job is not None
    assert result.job.status is JobStatus.PARTIAL
    assert result.job.translated_text is None
    assert result.job.error == "timeout"
    assert result.job.source_text == "World"


@pytest.mark.parametrize("error", ["timeout", "http_error", "http_429", "http_503"])
def test_live_retries_translation_after_delay_without_repeating_ocr(error: str) -> None:
    now = [10.0]
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator(translated_text=None, status=JobStatus.FAILURE, error=error)
    service = OcrTranslateService(ocr, translator, clock=lambda: now[0])
    result = _advance(service)

    now[0] = 11.9
    waiting = _advance(service, result.memory)
    assert waiting.action == LIVE_SKIP_FRAME
    assert len(translator.calls) == 1

    translator._status = JobStatus.SUCCESS
    translator._translated_text = "你好"
    translator._error = None
    now[0] = 12.0
    recovered = _advance(service, waiting.memory)

    assert recovered.job is not None
    assert recovered.job.status is JobStatus.SUCCESS
    assert recovered.job.translated_text == "你好"
    assert recovered.job.ocr_model == "fake-ocr"
    assert len(ocr.calls) == 1
    assert len(translator.calls) == 2
    now[0] = 100.0
    assert _advance(service, recovered.memory).action == LIVE_SKIP_FRAME
    assert len(translator.calls) == 2


def test_live_retry_budget_and_delay_survive_frame_changes_with_same_text() -> None:
    now = [0.0]
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator(
        translated_text=None, status=JobStatus.FAILURE, error="timeout"
    )
    service = OcrTranslateService(ocr, translator, clock=lambda: now[0])
    result = _advance(service)

    for timestamp, frame, expected_calls in (
        (1.9, "frame-2", 1),
        (2.0, "frame-3", 2),
        (6.9, "frame-4", 2),
        (7.0, "frame-5", 3),
        (100.0, "frame-6", 3),
        (200.0, "frame-6", 3),
    ):
        now[0] = timestamp
        result = _advance(service, result.memory, frame=frame)
        assert len(translator.calls) == expected_calls
    assert result.job is None

    ocr._text = "New sentence"
    changed = _advance(service, result.memory, frame="frame-7")
    assert changed.job is not None
    assert changed.job.source_text == "New sentence"
    assert len(translator.calls) == 4
    now[0] = 202.0
    _advance(service, changed.memory, frame="frame-7")
    assert len(translator.calls) == 5


@pytest.mark.parametrize(
    "error", ["http_401", "translate_not_configured", "translate_output_truncated"]
)
def test_live_does_not_retry_permanent_translation_failure(error: str) -> None:
    now = [0.0]
    translator = FakeTranslator(translated_text=None, status=JobStatus.FAILURE, error=error)
    service = OcrTranslateService(FakeOcrEngine(), translator, clock=lambda: now[0])
    result = _advance(service)

    now[0] = 100.0
    assert _advance(service, result.memory).action == LIVE_SKIP_FRAME
    assert _advance(service, result.memory, frame="changed").action == LIVE_SKIP_TEXT
    assert len(translator.calls) == 1


def test_live_stop_prevents_pending_translation_retry() -> None:
    now = [0.0]
    ocr = FakeOcrEngine()
    translator = FakeTranslator(
        translated_text=None, status=JobStatus.FAILURE, error="timeout"
    )
    service = OcrTranslateService(ocr, translator, clock=lambda: now[0])
    result = _advance(service)

    now[0] = 100.0
    stopped = service.advance_live(
        b"frame",
        "image/png",
        "auto",
        "zh",
        frame_hash="frame",
        memory=result.memory,
        should_continue=lambda: False,
    )
    assert stopped.action == LIVE_STOPPED
    assert len(ocr.calls) == 1
    assert len(translator.calls) == 1


def test_live_ocr_failure_does_not_schedule_translation_retry() -> None:
    ocr = FakeOcrEngine(text=None, status=JobStatus.FAILURE, error="timeout")
    translator = FakeTranslator()
    service = OcrTranslateService(ocr, translator)
    result = _advance(service)

    assert _advance(service, result.memory).action == LIVE_SKIP_FRAME
    assert len(ocr.calls) == 1
    assert translator.calls == []


def _advance(
    service: OcrTranslateService,
    memory: LiveOcrMemory = LiveOcrMemory(),
    *,
    frame: str = "frame",
) -> LiveOcrAdvance:
    return service.advance_live(
        frame.encode(),
        "image/png",
        "auto",
        "zh",
        frame_hash=frame,
        memory=memory,
    )


def test_image_signature_is_stable_for_same_bytes() -> None:
    assert image_signature(b"abc") == image_signature(b"abc")
    assert image_signature(b"abc") != image_signature(b"abd")


def test_live_stop_after_ocr_does_not_start_translation() -> None:
    ocr = FakeOcrEngine(text="World")
    translator = FakeTranslator(translated_text="世界")
    service = OcrTranslateService(ocr, translator)
    checks = iter((True, False))
    memory = LiveOcrMemory(frame_hash="frame-1", ocr_text="Hello")

    result = service.advance_live(
        b"png",
        "image/png",
        "auto",
        "zh",
        frame_hash="frame-2",
        memory=memory,
        should_continue=lambda: next(checks),
    )

    assert result.action == LIVE_STOPPED
    assert result.memory == memory
    assert len(ocr.calls) == 1
    assert translator.calls == []
