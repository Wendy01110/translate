from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.interfaces.overlay import (
    _applescript_string,
    _prepare_overlay_window,
    _text_view_copy_payload,
    edit_menu_commands,
    format_overlay,
    overlay_becomes_key_only_if_needed,
    overlay_text_for_copy,
    paddle_first_load_message,
    should_center_overlay,
    should_focus_overlay,
)


def test_overlay_keeps_full_long_text() -> None:
    source = "one\n" * 80
    translation = "一\n" * 80
    content = format_overlay(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.SUCCESS,
            source_text=source,
            translated_text=translation,
        )
    )
    assert content.source == source
    assert content.translation == translation


def test_paddle_first_load_message_sets_download_expectation() -> None:
    message = paddle_first_load_message("PP-OCRv6_tiny")

    assert "PP-OCRv6_tiny" in message
    assert "尚无缓存" in message
    assert "后续识别通常会更快" in message


def test_overlay_copy_uses_selection_or_full_text() -> None:
    assert overlay_text_for_copy(selection="你好", full="你好世界") == "你好"
    assert overlay_text_for_copy(selection="", full="你好世界") == "你好世界"


def test_text_view_copy_payload_reads_selected_range() -> None:
    class _View:
        def string(self) -> str:
            return "你好世界"

        def selectedRange(self) -> tuple[int, int]:
            return (0, 2)

    assert _text_view_copy_payload(_View()) == "你好"

    class _Empty:
        def string(self) -> str:
            return "你好世界"

        def selectedRange(self) -> tuple[int, int]:
            return (0, 0)

    assert _text_view_copy_payload(_Empty()) == "你好世界"


def test_edit_menu_binds_command_c_to_copy() -> None:
    commands = dict((action, key) for _title, action, key in edit_menu_commands())
    assert commands["copy:"] == "c"
    assert commands["selectAll:"] == "a"
    assert overlay_becomes_key_only_if_needed() is False


def test_set_scrollable_text_writes_and_scrolls_to_top() -> None:
    from ai_translate.interfaces.overlay import _set_scrollable_text

    class _View:
        def __init__(self) -> None:
            self.value = ""
            self.scrolled = None

        def setString_(self, value: str) -> None:
            self.value = value

        def scrollRangeToVisible_(self, span: object) -> None:
            self.scrolled = span

    view = _View()
    _set_scrollable_text(view, "hello")
    assert view.value == "hello"
    assert view.scrolled == (0, 0)


def test_overlay_splits_source_and_translation() -> None:
    content = format_overlay(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.SUCCESS,
            source_text="Hello",
            translated_text="你好",
        )
    )
    assert content.title == "划词"
    assert content.source == "Hello"
    assert content.translation == "你好"
    assert content.footnote == ""


def test_overlay_footnote_marks_official_translate_source() -> None:
    content = format_overlay(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.SUCCESS,
            source_text="Hello",
            translated_text="你好",
            translate_model="deepl",
        )
    )
    assert content.footnote == "DeepL"


def test_overlay_ocr_footnote_marks_local_engine() -> None:
    content = format_overlay(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.SUCCESS,
            source_text="Hello",
            translated_text="你好",
            ocr_engine="vision",
        )
    )
    assert content.title == "OCR"
    assert content.footnote == "本机"


def test_overlay_ocr_footnote_marks_standard_and_advanced_tiers() -> None:
    standard = format_overlay(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.SUCCESS,
            source_text=None,
            translated_text="普通结果",
            ocr_text="source",
            ocr_engine="standard",
        )
    )
    advanced = format_overlay(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.SUCCESS,
            source_text=None,
            translated_text="高级结果",
            ocr_text="source",
            ocr_engine="model",
        )
    )
    assert standard.footnote == "普通"
    assert advanced.footnote == "高级"


def test_overlay_failure_puts_error_in_translation() -> None:
    content = format_overlay(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.FAILURE,
            source_text="Hello",
            translated_text=None,
            error="timeout",
        )
    )
    assert content.title == "划词失败"
    assert content.source == "Hello"
    assert content.translation == "timeout"


def test_overlay_explains_missing_accessibility() -> None:
    content = format_overlay(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.FAILURE,
            source_text=None,
            translated_text=None,
            error="accessibility_required",
        )
    )
    assert content.title == "需要权限"
    assert "辅助功能" in content.translation


def test_applescript_string_escapes_quotes() -> None:
    assert _applescript_string('say "hi"') == '"say \\"hi\\""'


def test_existing_overlay_does_not_recenter_or_refocus() -> None:
    assert should_center_overlay(created=True) is True
    assert should_center_overlay(created=False) is False
    assert should_focus_overlay(visible=False) is True
    assert should_focus_overlay(visible=True) is False


def test_overlay_window_stays_visible_when_app_is_inactive() -> None:
    class _Window:
        def __init__(self) -> None:
            self.hides_on_deactivate = True
            self.floating = False

        def setLevel_(self, _value: object) -> None:
            return None

        def setReleasedWhenClosed_(self, _value: object) -> None:
            return None

        def setHidesOnDeactivate_(self, value: object) -> None:
            self.hides_on_deactivate = value

        def setFloatingPanel_(self, value: object) -> None:
            self.floating = value

        def setBecomesKeyOnlyIfNeeded_(self, value: object) -> None:
            self.becomes_key_only_if_needed = value

        def setCollectionBehavior_(self, _value: object) -> None:
            return None

    window = _Window()
    window.becomes_key_only_if_needed = True
    _prepare_overlay_window(window)
    assert window.hides_on_deactivate is False
    assert window.floating is True
    assert window.becomes_key_only_if_needed is False
