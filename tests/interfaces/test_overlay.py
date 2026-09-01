import sys
from types import SimpleNamespace

import ai_translate.interfaces.overlay as overlay_module
from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.interfaces.overlay import (
    OVERLAY_COPY_BUTTON_TOOLTIP,
    OVERLAY_COPY_SUCCESS_SYMBOL_NAME,
    OVERLAY_COPY_SUCCESS_TOOLTIP,
    OVERLAY_COPY_SYMBOL_NAME,
    OVERLAY_RESULT_LABEL,
    OVERLAY_SOURCE_LABEL,
    OVERLAY_TARGET_LANGUAGE_LABEL,
    OVERLAY_TARGET_LANGUAGE_TOOLTIP,
    OVERLAY_TRANSLATE_BUTTON_TITLE,
    OVERLAY_TRANSLATE_BUTTON_TOOLTIP,
    OVERLAY_TRANSLATING_BUTTON_TITLE,
    OverlayPresenter,
    _AppKitBackend,
    _applescript_string,
    _configure_overlay_text_interaction,
    _prepare_overlay_chrome,
    _prepare_overlay_window,
    _set_overlay_pinned,
    _text_view_copy_payload,
    edit_menu_commands,
    format_macos_translation,
    format_overlay,
    format_translation_workspace,
    normalize_target_language_options,
    overlay_becomes_key_only_if_needed,
    overlay_copy_button_title,
    overlay_copy_symbol_name,
    overlay_pin_button_title,
    overlay_pin_symbol_name,
    overlay_text_for_copy,
    overlay_window_origin_for_point,
    overlay_window_layout,
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
    assert content.source_editable is True


def test_translation_workspace_makes_ocr_source_editable_for_manual_retry() -> None:
    content = format_translation_workspace(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.PARTIAL,
            source_text=None,
            translated_text=None,
            ocr_text="OCR source",
            error="timeout",
        )
    )

    assert content.title == "翻译"
    assert content.source == "OCR source"
    assert content.translation == "timeout"
    assert content.source_editable is True


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
    assert content.source_editable is True


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
    assert content.source_editable is False


def test_macos_translation_workspace_unifies_input_selection_and_ocr() -> None:
    empty = format_macos_translation()
    selection = format_macos_translation(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.SUCCESS,
            source_text="Hello",
            translated_text="你好",
        )
    )
    ocr = format_macos_translation(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.SUCCESS,
            source_text=None,
            translated_text="OCR 译文",
            ocr_text="OCR source",
            ocr_engine="vision",
        )
    )

    assert (empty.title, empty.source, empty.translation) == ("翻译", "", "")
    assert (selection.title, selection.source, selection.translation) == (
        "翻译",
        "Hello",
        "你好",
    )
    assert (ocr.title, ocr.source, ocr.translation, ocr.footnote) == (
        "翻译",
        "OCR source",
        "OCR 译文",
        "本机",
    )
    assert empty.source_editable is True
    assert selection.source_editable is True
    assert ocr.source_editable is True


def test_overlay_ocr_footnote_marks_local_and_remote_advanced_tiers() -> None:
    local_advanced = format_overlay(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.SUCCESS,
            source_text=None,
            translated_text="本地高级结果",
            ocr_text="source",
            ocr_engine="paddle",
        )
    )
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
    assert local_advanced.footnote == "本地高级"
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


def test_overlay_pin_button_describes_next_action() -> None:
    assert overlay_pin_button_title(pinned=False) == "置顶"
    assert overlay_pin_button_title(pinned=True) == "取消置顶"
    assert overlay_pin_symbol_name(pinned=False) == "pin"
    assert overlay_pin_symbol_name(pinned=True) == "pin.fill"


def test_overlay_visible_static_copy_matches_reference() -> None:
    assert (OVERLAY_SOURCE_LABEL, OVERLAY_RESULT_LABEL) == ("原文", "译文")
    assert OVERLAY_TARGET_LANGUAGE_LABEL == "目标语言"
    assert OVERLAY_TARGET_LANGUAGE_TOOLTIP == "切换本次运行的目标语言"
    assert OVERLAY_TRANSLATE_BUTTON_TITLE == "翻译"
    assert OVERLAY_TRANSLATING_BUTTON_TITLE == "翻译中…"
    assert OVERLAY_TRANSLATE_BUTTON_TOOLTIP == "翻译原文（⌘↵）"
    assert OVERLAY_COPY_BUTTON_TOOLTIP == "复制译文"
    assert OVERLAY_COPY_SUCCESS_TOOLTIP == "已复制"
    assert OVERLAY_COPY_SYMBOL_NAME == "doc.on.doc"
    assert OVERLAY_COPY_SUCCESS_SYMBOL_NAME == "checkmark"
    assert overlay_copy_button_title(copied=False) == "复制译文"
    assert overlay_copy_button_title(copied=True) == "已复制"
    assert overlay_copy_symbol_name(copied=False) == "doc.on.doc"
    assert overlay_copy_symbol_name(copied=True) == "checkmark"


def test_target_language_options_are_normalized_and_keep_custom_current() -> None:
    options = normalize_target_language_options(
        (("ZH", "中文"), ("en", "英语"), ("zh", "重复"), ("", "空")),
        " JA ",
    )

    assert options == (("zh", "中文"), ("en", "英语"), ("ja", "ja"))

    try:
        normalize_target_language_options((), "")
    except ValueError as exc:
        assert str(exc) == "at least one target language is required"
    else:
        raise AssertionError("empty target-language options must be rejected")


def test_overlay_source_is_editable_and_translation_is_read_only() -> None:
    class _View:
        def __init__(self) -> None:
            self.editable = None
            self.selectable = None
            self.allows_undo = None
            self.automatic = []

        def setEditable_(self, value: bool) -> None:
            self.editable = value

        def setSelectable_(self, value: bool) -> None:
            self.selectable = value

        def setAllowsUndo_(self, value: bool) -> None:
            self.allows_undo = value

        def setAutomaticQuoteSubstitutionEnabled_(self, value: bool) -> None:
            self.automatic.append(value)

        def setAutomaticDashSubstitutionEnabled_(self, value: bool) -> None:
            self.automatic.append(value)

        def setAutomaticTextReplacementEnabled_(self, value: bool) -> None:
            self.automatic.append(value)

        def setAutomaticSpellingCorrectionEnabled_(self, value: bool) -> None:
            self.automatic.append(value)

    source = _View()
    translation = _View()

    _configure_overlay_text_interaction(source, editable=True)
    _configure_overlay_text_interaction(translation, editable=False)

    assert (source.editable, source.selectable, source.allows_undo) == (
        True,
        True,
        True,
    )
    assert (translation.editable, translation.selectable, translation.allows_undo) == (
        False,
        True,
        False,
    )
    assert source.automatic == [False, False, False, False]
    assert translation.automatic == [False, False, False, False]


def test_overlay_icon_styles_make_action_feedback_visible(monkeypatch) -> None:
    styles = []
    button = object()
    monkeypatch.setattr(
        overlay_module,
        "_style_icon_button",
        lambda target, **style: styles.append((target, style)),
    )

    overlay_module._style_pin_button(button, pinned=False)
    overlay_module._style_pin_button(button, pinned=True)
    overlay_module._style_copy_button(button, copied=False)
    overlay_module._style_copy_button(button, copied=True)

    assert styles[0][1] == {
        "symbol": "pin",
        "accessibility_label": "置顶",
        "background": "#E5E5FF",
        "tint": "#1F2430",
    }
    assert styles[1][1] == {
        "symbol": "pin.fill",
        "accessibility_label": "取消置顶",
        "background": "#4F46E5",
        "tint": "#FFFFFF",
    }
    assert styles[2][1]["symbol"] == "doc.on.doc"
    assert styles[2][1]["background"] == "#F1F2F6"
    assert styles[3][1]["symbol"] == "checkmark"
    assert styles[3][1]["accessibility_label"] == "已复制"
    assert styles[3][1]["background"] == "#E5E5FF"
    assert styles[3][1]["tint"] == "#4F46E5"


def test_wide_overlay_uses_two_columns_and_header_icon_actions() -> None:
    layout = overlay_window_layout(720.0, 520.0)

    assert layout.mode == "wide"
    assert not hasattr(layout, "title")
    assert layout.source_editor.y == layout.result_editor.y
    assert layout.source_editor.height == layout.result_editor.height
    assert layout.source_editor.right < layout.result_editor.x
    assert layout.source_label.x == layout.source_editor.x
    assert layout.result_label.x == layout.result_editor.x
    assert layout.source_editor.y == 28.0
    assert layout.source_editor.height == 386.0
    assert layout.translate_button.right < layout.pin_button.x
    assert layout.pin_button.right < layout.copy_button.x
    assert layout.translate_button.y == layout.pin_button.y == layout.copy_button.y
    assert layout.copy_button.right <= 720.0
    assert layout.target_language_label.x == 28.0
    assert layout.target_language_label.right < layout.target_language_popup.x
    assert layout.target_language_popup.right < layout.helper.x
    assert layout.helper.right < layout.translate_button.x
    assert layout.target_language_popup.y > layout.translate_button.y
    assert layout.source_label.top < layout.target_language_popup.y


def test_compact_overlay_stacks_content_and_keeps_header_actions() -> None:
    layout = overlay_window_layout(440.0, 520.0)

    assert layout.mode == "compact"
    assert layout.source_editor.x == layout.result_editor.x
    assert layout.source_editor.width == layout.result_editor.width
    assert layout.source_editor.y > layout.result_label.top
    assert layout.result_editor.y == 24.0
    assert layout.source_editor.height == layout.result_editor.height == 174.0
    assert layout.translate_button.right < layout.pin_button.x
    assert layout.pin_button.right < layout.copy_button.x
    assert layout.copy_button.right <= 440.0
    assert layout.target_language_label.x == 24.0
    assert layout.target_language_label.right < layout.target_language_popup.x
    assert layout.target_language_popup.width == 104.0
    assert layout.target_language_popup.right < layout.helper.x
    assert layout.helper.right < layout.translate_button.x
    assert layout.helper.width > 0.0
    assert layout.source_label.top < layout.target_language_popup.y


def test_overlay_layout_rejects_non_positive_dimensions() -> None:
    for width, height in ((0.0, 520.0), (720.0, 0.0), (-1.0, 520.0)):
        try:
            overlay_window_layout(width, height)
        except ValueError as exc:
            assert str(exc) == "overlay window dimensions must be positive"
        else:
            raise AssertionError("invalid dimensions must be rejected")


def test_overlay_centers_on_the_screen_containing_the_pointer() -> None:
    primary = overlay_module.OverlayFrame(0.0, 0.0, 1440.0, 900.0)
    secondary = overlay_module.OverlayFrame(1440.0, 0.0, 1920.0, 1080.0)

    origin = overlay_window_origin_for_point(
        window_width=720.0,
        window_height=520.0,
        screens=(primary, secondary),
        point=(2200.0, 500.0),
    )

    assert origin == (2040.0, 280.0)


def test_overlay_chrome_uses_runtime_appkit_constants(monkeypatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(
            NSWindowTitleHidden=11,
            NSTitlebarSeparatorStyleLine=22,
        ),
    )

    class _Window:
        def setTitle_(self, value: str) -> None:
            self.title = value

        def setContentMinSize_(self, value: object) -> None:
            self.content_min_size = value

        def setTitleVisibility_(self, value: object) -> None:
            self.title_visibility = value

        def setTitlebarAppearsTransparent_(self, value: object) -> None:
            self.titlebar_transparent = value

        def setTitlebarSeparatorStyle_(self, value: object) -> None:
            self.titlebar_separator = value

    window = _Window()
    _prepare_overlay_chrome(window)

    assert window.title == "翻译"
    assert window.content_min_size == (440.0, 480.0)
    assert window.title_visibility == 11
    assert window.titlebar_transparent is False
    assert window.titlebar_separator == 22


def test_appkit_overlay_toggle_updates_level_button_and_process_state(
    monkeypatch,
) -> None:
    calls = []
    styles = []

    class _Window:
        def __init__(self) -> None:
            self.front_count = 0

        def orderFrontRegardless(self) -> None:
            self.front_count += 1

    class _Button:
        def __init__(self) -> None:
            self.title = "置顶"

        def setTitle_(self, title: str) -> None:
            self.title = title

    window = _Window()
    button = _Button()
    backend = _AppKitBackend.__new__(_AppKitBackend)
    backend._window = window
    backend._pin_button = button
    backend._pinned = False
    monkeypatch.setattr(
        overlay_module,
        "_set_overlay_pinned",
        lambda target, *, pinned: calls.append((target, pinned)),
    )

    def record_style(target: object, *, pinned: bool) -> None:
        styles.append((target, pinned))
        target.setTitle_(overlay_pin_button_title(pinned=pinned))

    monkeypatch.setattr(
        overlay_module,
        "_style_pin_button",
        record_style,
    )

    backend.toggle_pin()

    assert backend._pinned is True
    assert calls == [(window, True)]
    assert styles == [(button, True)]
    assert button.title == "取消置顶"
    assert window.front_count == 1

    backend.toggle_pin()

    assert backend._pinned is False
    assert calls[-1] == (window, False)
    assert styles[-1] == (button, False)
    assert button.title == "置顶"
    assert window.front_count == 2


def test_unpinned_overlay_hides_after_losing_key_status() -> None:
    class _Window:
        def __init__(self) -> None:
            self.order_out_count = 0

        def orderOut_(self, _sender) -> None:
            self.order_out_count += 1

    window = _Window()
    backend = _AppKitBackend.__new__(_AppKitBackend)
    backend._window = window
    backend._pinned = False
    backend._needs_focus = False
    backend._handling_resign_key = False

    backend.window_did_resign_key()

    assert window.order_out_count == 1
    assert backend._needs_focus is True

    backend._pinned = True
    backend.window_did_resign_key()
    assert window.order_out_count == 1


def test_appkit_overlay_copy_button_copies_translation_only(monkeypatch) -> None:
    copied = []
    styles = []
    scheduled = []

    class _Translation:
        def __init__(self, value: str) -> None:
            self.value = value

        def string(self) -> str:
            return self.value

    backend = _AppKitBackend.__new__(_AppKitBackend)
    backend._translation = _Translation("译文内容")
    backend._copy_button = object()
    backend._copy_feedback_generation = 0
    monkeypatch.setattr(overlay_module, "_copy_plain_text", copied.append)
    monkeypatch.setattr(
        overlay_module,
        "_style_copy_button",
        lambda button, *, copied: styles.append((button, copied)),
    )
    monkeypatch.setattr(
        overlay_module,
        "_schedule_overlay_feedback",
        lambda delay, callback, *args: scheduled.append((delay, callback, args)),
    )

    backend.copy_translation()

    assert copied == ["译文内容"]
    assert styles == [(backend._copy_button, True)]
    assert len(scheduled) == 1
    delay, callback, args = scheduled[0]
    assert delay == 1.2

    callback(*args)
    assert styles[-1] == (backend._copy_button, False)

    backend._translation = _Translation("")
    backend.copy_translation()
    assert copied == ["译文内容"]
    assert len(scheduled) == 1


def test_overlay_presenter_forwards_typed_translation_callback() -> None:
    callbacks = []

    class _Backend:
        def set_translate(self, callback) -> None:
            callbacks.append(callback)

    presenter = OverlayPresenter.__new__(OverlayPresenter)
    presenter._impl = _Backend()
    translate = lambda text: text

    presenter.set_translate(translate)

    assert callbacks == [translate]


def test_overlay_presenter_forwards_target_language_configuration() -> None:
    configured = []
    selected = []

    class _Backend:
        def configure_target_languages(self, options, *, current, on_change) -> None:
            configured.append((options, current, on_change))

        def set_target_language(self, target_language: str) -> None:
            selected.append(target_language)

    presenter = OverlayPresenter.__new__(OverlayPresenter)
    presenter._impl = _Backend()
    on_change = lambda target: target
    options = (("zh", "中文"), ("en", "英语"))

    presenter.configure_target_languages(
        options,
        current="zh",
        on_change=on_change,
    )
    presenter.set_target_language("en")

    assert configured == [(options, "zh", on_change)]
    assert selected == ["en"]


def test_appkit_target_language_change_updates_session_callback() -> None:
    changed = []
    backend = _AppKitBackend.__new__(_AppKitBackend)
    backend._target_language_label = None
    backend._target_language_popup = None
    backend._target_language_options = ()
    backend._target_language = ""
    backend._target_language_changed = None

    backend.configure_target_languages(
        (("zh", "中文"), ("en", "英语"), ("ja", "日语")),
        current="zh",
        on_change=changed.append,
    )
    backend.target_language_changed(2)
    backend.target_language_changed(2)

    assert backend._target_language == "ja"
    assert changed == ["ja"]

    backend.set_target_language("de")
    assert backend._target_language == "de"
    assert backend._target_language_options[-1] == ("de", "de")
    assert changed == ["ja"]


def test_overlay_presenter_uses_same_backend_for_input_selection_and_ocr() -> None:
    shown = []
    input_contents = []

    class _Backend:
        def show(self, content) -> None:
            shown.append(content)

        def show_input(self, content) -> None:
            input_contents.append(content)

    presenter = OverlayPresenter.__new__(OverlayPresenter)
    presenter._impl = _Backend()

    presenter.show_input()
    presenter.show(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.SUCCESS,
            source_text="selection",
            translated_text="划词译文",
        )
    )
    presenter.show(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.SUCCESS,
            source_text=None,
            translated_text="OCR 译文",
            ocr_text="ocr",
        )
    )

    assert len(input_contents) == 1
    assert len(shown) == 2
    assert input_contents[0].title == "翻译"
    assert [content.title for content in shown] == ["翻译", "翻译"]
    assert all(content.source_editable for content in input_contents + shown)


def test_overlay_translate_action_reads_edited_source_and_starts_once(
    monkeypatch,
) -> None:
    threads = []
    styles = []

    class _Source:
        def string(self) -> str:
            return "edited source"

    class _Helper:
        def setStringValue_(self, value: str) -> None:
            self.value = value

    class _Button:
        def setHidden_(self, value: bool) -> None:
            self.hidden = value

    class _Thread:
        def __init__(self, *, target, args, daemon) -> None:
            threads.append((target, args, daemon))

        def start(self) -> None:
            self.started = True

    backend = _AppKitBackend.__new__(_AppKitBackend)
    backend._busy = False
    backend._source_editable = True
    backend._translate = lambda text: text
    backend._source = _Source()
    backend._helper = _Helper()
    backend._translate_button = _Button()
    monkeypatch.setattr(overlay_module.threading, "Thread", _Thread)
    monkeypatch.setattr(
        overlay_module,
        "_style_translate_button",
        lambda button, *, enabled, busy: styles.append((enabled, busy)),
    )

    backend.request_translate()
    backend.request_translate()

    assert backend._busy is True
    assert backend._helper.value == "翻译中…"
    assert styles == [(False, True)]
    assert len(threads) == 1
    target, args, daemon = threads[0]
    assert target == backend._run_typed_translation
    assert args == ("edited source", backend._translate)
    assert daemon is True


def test_overlay_translate_button_only_appears_for_editable_content(
    monkeypatch,
) -> None:
    styles = []

    class _Button:
        def setHidden_(self, value: bool) -> None:
            self.hidden = value

    backend = _AppKitBackend.__new__(_AppKitBackend)
    backend._translate_button = _Button()
    backend._translate = lambda text: text
    backend._busy = False
    monkeypatch.setattr(
        overlay_module,
        "_style_translate_button",
        lambda button, *, enabled, busy: styles.append((enabled, busy)),
    )

    backend._source_editable = True
    backend._sync_translate_button()
    assert backend._translate_button.hidden is False
    assert styles[-1] == (True, False)

    backend._busy = True
    backend._sync_translate_button()
    assert backend._translate_button.hidden is False
    assert styles[-1] == (False, True)

    backend._source_editable = False
    backend._sync_translate_button()
    assert backend._translate_button.hidden is True
    assert styles[-1] == (False, True)


def test_overlay_typed_translation_updates_result_and_restores_action(
    monkeypatch,
) -> None:
    written = []
    synced = []
    reset = []

    class _Field:
        def setStringValue_(self, value: str) -> None:
            self.value = value

    class _Translation:
        pass

    backend = _AppKitBackend.__new__(_AppKitBackend)
    backend._busy = True
    backend._window = None
    backend._helper = _Field()
    backend._translation = _Translation()
    monkeypatch.setattr(backend, "_sync_translate_button", lambda: synced.append(True))
    monkeypatch.setattr(backend, "_reset_copy_feedback", lambda: reset.append(True))
    monkeypatch.setattr(
        overlay_module,
        "_set_scrollable_text",
        lambda target, value: written.append((target, value)),
    )

    backend._show_typed_translation(
        TranslateJob(
            kind=JobKind.SELECTION,
            status=JobStatus.SUCCESS,
            source_text="Hello",
            translated_text="你好",
            translate_model="deepl",
        )
    )

    assert backend._busy is False
    assert synced == [True]
    assert backend._helper.value == "DeepL"
    assert written == [(backend._translation, "你好")]
    assert reset == [True]


def test_overlay_window_defaults_to_normal_level_when_app_is_inactive(
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(
            NSFloatingWindowLevel=3,
            NSNormalWindowLevel=0,
            NSWindowCollectionBehaviorCanJoinAllSpaces=1,
            NSWindowCollectionBehaviorFullScreenAuxiliary=2,
            NSWindowCollectionBehaviorMoveToActiveSpace=4,
        ),
    )

    class _Window:
        def __init__(self) -> None:
            self.hides_on_deactivate = True
            self.floating = False
            self.level = None
            self.collection_behavior = None

        def setLevel_(self, value: object) -> None:
            self.level = value

        def setReleasedWhenClosed_(self, _value: object) -> None:
            return None

        def setHidesOnDeactivate_(self, value: object) -> None:
            self.hides_on_deactivate = value

        def setFloatingPanel_(self, value: object) -> None:
            self.floating = value

        def setBecomesKeyOnlyIfNeeded_(self, value: object) -> None:
            self.becomes_key_only_if_needed = value

        def setCollectionBehavior_(self, value: object) -> None:
            self.collection_behavior = value

    window = _Window()
    window.becomes_key_only_if_needed = True
    _prepare_overlay_window(window, pinned=False)
    assert window.hides_on_deactivate is False
    assert window.level == 0
    assert window.floating is False
    assert window.collection_behavior == 6
    assert window.becomes_key_only_if_needed is False

    _set_overlay_pinned(window, pinned=True)
    assert window.level == 3
    assert window.floating is True
    assert window.collection_behavior == 3

    _set_overlay_pinned(window, pinned=False)
    assert window.level == 0
    assert window.floating is False
    assert window.collection_behavior == 6
