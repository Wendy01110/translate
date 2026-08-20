from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.interfaces.input_box import (
    format_input_translation,
    should_center_input,
)


def _job(**overrides: object) -> TranslateJob:
    payload = {
        "kind": JobKind.SELECTION,
        "status": JobStatus.SUCCESS,
        "source_text": "Hello",
        "translated_text": "你好",
        "error": None,
    }
    payload.update(overrides)
    return TranslateJob(**payload)


def test_format_input_translation_uses_translated_text() -> None:
    assert format_input_translation(_job()) == "你好"


def test_format_input_translation_explains_empty_text() -> None:
    text = format_input_translation(
        _job(status=JobStatus.FAILURE, translated_text=None, error="empty_text")
    )
    assert text == "请输入要翻译的文字。"


def test_format_input_translation_explains_busy() -> None:
    text = format_input_translation(
        _job(status=JobStatus.FAILURE, translated_text=None, error="busy")
    )
    assert text == "正在翻译，请稍后再试。"


def test_format_input_translation_keeps_unknown_error() -> None:
    text = format_input_translation(
        _job(status=JobStatus.FAILURE, translated_text=None, error="timeout")
    )
    assert text == "timeout"


def test_should_center_input_only_when_hidden() -> None:
    assert should_center_input(visible=False) is True
    assert should_center_input(visible=True) is False
