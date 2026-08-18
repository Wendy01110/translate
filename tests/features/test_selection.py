from ai_translate.core.models import JobKind, JobStatus
from ai_translate.features.selection import SelectionTranslateService
from tests.support import FakeTranslator


def test_empty_text_fails_without_calling_translator() -> None:
    translator = FakeTranslator()
    service = SelectionTranslateService(translator)

    job = service.translate_text("   ", source_lang="auto", target_lang="zh")

    assert job.kind is JobKind.SELECTION
    assert job.status is JobStatus.FAILURE
    assert job.error == "empty_text"
    assert translator.calls == []


def test_successful_selection_translation() -> None:
    translator = FakeTranslator(translated_text="你好")
    service = SelectionTranslateService(translator)

    job = service.translate_text("Hello", source_lang="en", target_lang="zh")

    assert job.status is JobStatus.SUCCESS
    assert job.translated_text == "你好"
    assert job.source_text == "Hello"
    assert job.translate_model == "fake-translate"
    assert translator.calls[0].text == "Hello"
    assert translator.calls[0].source_lang == "en"


def test_translator_failure_is_preserved() -> None:
    translator = FakeTranslator(
        translated_text=None,
        status=JobStatus.FAILURE,
        error="timeout",
    )
    service = SelectionTranslateService(translator)

    job = service.translate_text("Hello", source_lang="auto", target_lang="zh")

    assert job.status is JobStatus.FAILURE
    assert job.error == "timeout"
    assert job.translated_text is None
