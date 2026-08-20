from ai_translate.core.models import JobKind, JobStatus, ScreenRect
from ai_translate.features.ocr_translate import (
    LIVE_SHOW,
    LIVE_SKIP_FRAME,
    LIVE_SKIP_TEXT,
    LIVE_STOPPED,
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
