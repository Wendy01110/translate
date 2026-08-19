from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.interfaces.overlay import (
    _applescript_string,
    _prepare_overlay_window,
    format_overlay,
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

        def setCollectionBehavior_(self, _value: object) -> None:
            return None

    window = _Window()
    _prepare_overlay_window(window)
    assert window.hides_on_deactivate is False
    assert window.floating is True
