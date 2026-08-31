from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.interfaces.input_box import (
    INPUT_RESULT_LABEL,
    INPUT_RESULT_PLACEHOLDER,
    INPUT_SOURCE_LABEL,
    INPUT_SOURCE_PLACEHOLDER,
    INPUT_TRANSLATE_BUTTON,
    INPUT_TRANSLATE_SHORTCUT,
    INPUT_WINDOW_HELPER,
    INPUT_WINDOW_TITLE,
    format_input_translation,
    input_window_layout,
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


def test_input_window_visible_copy_matches_the_design_spec() -> None:
    assert (
        INPUT_WINDOW_TITLE,
        INPUT_WINDOW_HELPER,
        INPUT_SOURCE_LABEL,
        INPUT_SOURCE_PLACEHOLDER,
        INPUT_RESULT_LABEL,
        INPUT_RESULT_PLACEHOLDER,
        INPUT_TRANSLATE_BUTTON,
        INPUT_TRANSLATE_SHORTCUT,
    ) == (
        "输入翻译",
        "输入文字，按 ⌘↵ 翻译",
        "原文",
        "在这里粘贴或输入文字…",
        "译文",
        "译文会显示在这里",
        "翻译",
        "⌘ ↵",
    )


def test_wide_input_window_uses_two_non_overlapping_columns() -> None:
    layout = input_window_layout(720.0, 520.0)

    assert layout.mode == "wide"
    assert layout.source_editor.y == layout.result_editor.y
    assert layout.source_editor.height == layout.result_editor.height
    assert layout.source_editor.right < layout.result_editor.x
    assert layout.source_label.x == layout.source_editor.x
    assert layout.result_label.x == layout.result_editor.x
    assert layout.source_editor.y > layout.separator.top
    assert layout.button.right <= 720.0


def test_compact_input_window_stacks_source_above_result() -> None:
    layout = input_window_layout(440.0, 520.0)

    assert layout.mode == "compact"
    assert layout.source_editor.x == layout.result_editor.x
    assert layout.source_editor.width == layout.result_editor.width
    assert layout.source_editor.y > layout.result_label.top
    assert layout.result_editor.y > layout.separator.top
    assert layout.source_label.top <= layout.helper.y
    assert layout.button.right <= 440.0


def test_input_window_layout_rejects_non_positive_dimensions() -> None:
    for width, height in ((0.0, 520.0), (720.0, 0.0), (-1.0, 520.0)):
        try:
            input_window_layout(width, height)
        except ValueError as exc:
            assert str(exc) == "input window dimensions must be positive"
        else:
            raise AssertionError("invalid dimensions must be rejected")
