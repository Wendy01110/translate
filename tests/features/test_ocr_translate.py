from ai_translate.core.models import JobKind, JobStatus
from ai_translate.features.ocr_translate import OcrTranslateService
from tests.support import FakeOcrEngine, FakeTranslator


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
