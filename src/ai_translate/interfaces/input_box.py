from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from ai_translate.core.models import JobKind, JobStatus, TranslateJob

INPUT_WINDOW_TITLE = "输入翻译"
INPUT_WINDOW_HELPER = "输入文字，按 ⌘↵ 翻译"
INPUT_SOURCE_LABEL = "原文"
INPUT_SOURCE_PLACEHOLDER = "在这里粘贴或输入文字…"
INPUT_RESULT_LABEL = "译文"
INPUT_RESULT_PLACEHOLDER = "译文会显示在这里"
INPUT_TRANSLATE_BUTTON = "翻译"
INPUT_TRANSLATE_SHORTCUT = "⌘ ↵"

_INPUT_DEFAULT_WIDTH = 720.0
_INPUT_DEFAULT_HEIGHT = 520.0
_INPUT_MIN_WIDTH = 440.0
_INPUT_MIN_HEIGHT = 480.0
_INPUT_WIDE_BREAKPOINT = 640.0

_INPUT_ERRORS = {
    "empty_text": "请输入要翻译的文字。",
    "busy": "正在翻译，请稍后再试。",
    "text_too_long": "文字太长。",
    "unsupported_language": "当前翻译源不支持这个语言。",
    "http_403": "网页翻译被拒绝，可稍后再试或改用官方密钥源。",
    "http_429": "翻译请求太频繁，请稍后再试。",
    "translate_not_configured": "翻译模型未配置。",
}


def format_input_translation(job: TranslateJob) -> str:
    if job.status is JobStatus.SUCCESS and job.translated_text:
        return job.translated_text
    if job.error:
        return _INPUT_ERRORS.get(job.error, job.error)
    return ""


def should_center_input(*, visible: bool) -> bool:
    return not visible


@dataclass(frozen=True, slots=True)
class InputFrame:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class InputWindowLayout:
    mode: str
    title: InputFrame
    helper: InputFrame
    source_label: InputFrame
    source_editor: InputFrame
    result_label: InputFrame
    result_editor: InputFrame
    separator: InputFrame
    status: InputFrame
    shortcut: InputFrame
    button: InputFrame


def input_window_layout(width: float, height: float) -> InputWindowLayout:
    """Return AppKit frames for the wide and compact input-window layouts."""

    if width <= 0.0 or height <= 0.0:
        raise ValueError("input window dimensions must be positive")

    wide = width >= _INPUT_WIDE_BREAKPOINT
    margin = 28.0 if wide else 24.0
    title = InputFrame(margin, height - 62.0, width - (margin * 2.0), 28.0)
    helper = InputFrame(margin, height - 88.0, width - (margin * 2.0), 18.0)
    label_top = height - 112.0
    editor_top = label_top - 26.0
    editor_bottom = 88.0
    label_height = 18.0
    label_gap = 8.0

    if wide:
        column_gap = 20.0
        editor_width = (width - (margin * 2.0) - column_gap) / 2.0
        editor_height = max(80.0, editor_top - editor_bottom)
        source_editor = InputFrame(
            margin,
            editor_bottom,
            editor_width,
            editor_height,
        )
        result_editor = InputFrame(
            margin + editor_width + column_gap,
            editor_bottom,
            editor_width,
            editor_height,
        )
        source_label = InputFrame(
            source_editor.x,
            source_editor.top + label_gap,
            source_editor.width,
            label_height,
        )
        result_label = InputFrame(
            result_editor.x,
            result_editor.top + label_gap,
            result_editor.width,
            label_height,
        )
        mode = "wide"
    else:
        block_gap = 16.0
        content_width = width - (margin * 2.0)
        editor_height = max(
            72.0,
            (
                label_top
                - editor_bottom
                - (label_height * 2.0)
                - (label_gap * 2.0)
                - block_gap
            )
            / 2.0,
        )
        result_editor = InputFrame(
            margin,
            editor_bottom,
            content_width,
            editor_height,
        )
        result_label = InputFrame(
            margin,
            result_editor.top + label_gap,
            content_width,
            label_height,
        )
        source_editor = InputFrame(
            margin,
            result_label.top + block_gap,
            content_width,
            editor_height,
        )
        source_label = InputFrame(
            margin,
            source_editor.top + label_gap,
            content_width,
            label_height,
        )
        mode = "compact"

    button = InputFrame(width - margin - 100.0, 17.0, 100.0, 36.0)
    shortcut = InputFrame(button.x - 58.0, 25.0, 46.0, 18.0)
    status = InputFrame(
        margin,
        25.0,
        max(40.0, shortcut.x - margin - 16.0),
        18.0,
    )
    return InputWindowLayout(
        mode=mode,
        title=title,
        helper=helper,
        source_label=source_label,
        source_editor=source_editor,
        result_label=result_label,
        result_editor=result_editor,
        separator=InputFrame(0.0, 68.0, width, 1.0),
        status=status,
        shortcut=shortcut,
        button=button,
    )


class InputTranslatePresenter:
    def __init__(self, *, translate: Callable[[str], TranslateJob]) -> None:
        self._translate = translate
        self._window: _InputWindow | None = None

    def show(self) -> None:
        if self._window is None:
            self._window = _InputWindow(translate=self._translate)
        self._window.show()


class _InputWindow:
    def __init__(self, *, translate: Callable[[str], TranslateJob]) -> None:
        from AppKit import (
            NSBackingStoreBuffered,
            NSButton,
            NSEventModifierFlagCommand,
            NSMakeRect,
            NSWindow,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )

        self._translate = translate
        self._busy = False
        self._width = _INPUT_DEFAULT_WIDTH
        self._height = _INPUT_DEFAULT_HEIGHT
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0.0, 0.0, self._width, self._height),
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_(INPUT_WINDOW_TITLE)
        window.setMinSize_((_INPUT_MIN_WIDTH, _INPUT_MIN_HEIGHT))
        set_title_visibility = getattr(window, "setTitleVisibility_", None)
        if callable(set_title_visibility):
            set_title_visibility(1)
        set_titlebar_transparent = getattr(
            window,
            "setTitlebarAppearsTransparent_",
            None,
        )
        if callable(set_titlebar_transparent):
            set_titlebar_transparent(True)
        _prepare_input_window(window)
        content = window.contentView()
        if content is None:
            raise RuntimeError("input window has no content view")
        _style_window_content(window, content)
        controller = _input_controller_class().alloc().init()
        controller.owner = self
        window.setDelegate_(controller)
        title = _text_label(
            content,
            INPUT_WINDOW_TITLE,
            font_size=22.0,
            weight="semibold",
            color="#1F2430",
        )
        helper = _text_label(
            content,
            INPUT_WINDOW_HELPER,
            font_size=13.0,
            color="#6B7280",
        )
        source_label = _text_label(
            content,
            INPUT_SOURCE_LABEL,
            font_size=13.0,
            weight="medium",
            color="#1F2430",
        )
        source_scroll, source = _scrolling_text(
            content,
            placeholder=INPUT_SOURCE_PLACEHOLDER,
            editable=True,
            accent_border=True,
        )
        result_label = _text_label(
            content,
            INPUT_RESULT_LABEL,
            font_size=13.0,
            weight="medium",
            color="#1F2430",
        )
        result_scroll, result = _scrolling_text(
            content,
            placeholder=INPUT_RESULT_PLACEHOLDER,
            editable=False,
            accent_border=False,
        )
        separator = _separator(content)
        status = _text_label(
            content,
            "",
            font_size=12.0,
            color="#6B7280",
        )
        shortcut = _text_label(
            content,
            INPUT_TRANSLATE_SHORTCUT,
            font_size=12.0,
            weight="medium",
            color="#8A91A3",
            alignment="center",
        )
        button = NSButton.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 100.0, 36.0))
        _style_primary_button(button, enabled=True)
        button.setTarget_(controller)
        button.setAction_("translateInput:")
        button.setKeyEquivalent_("\r")
        button.setKeyEquivalentModifierMask_(NSEventModifierFlagCommand)
        content.addSubview_(button)
        self._window = window
        self._content = content
        self._controller = controller
        self._title = title
        self._helper = helper
        self._source_label = source_label
        self._source_scroll = source_scroll
        self._source = source
        self._result_label = result_label
        self._result_scroll = result_scroll
        self._result = result
        self._separator = separator
        self._status = status
        self._shortcut = shortcut
        self._button = button
        self.layout()

    def show(self) -> None:
        from AppKit import NSApp, NSApplicationActivationPolicyRegular

        visible = bool(self._window.isVisible())
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        unhide = getattr(NSApp, "unhide_", None)
        if callable(unhide):
            unhide(None)
        NSApp.activateIgnoringOtherApps_(True)
        if should_center_input(visible=visible):
            self._window.center()
        self._window.makeKeyAndOrderFront_(None)
        self._window.orderFrontRegardless()
        self._window.makeFirstResponder_(self._source)

    def request_translate(self) -> None:
        if self._busy:
            self._status.setStringValue_("正在翻译，请稍后再试。")
            return
        text = str(self._source.string())
        self._busy = True
        _style_primary_button(self._button, enabled=False)
        self._status.setStringValue_("翻译中…")
        self._result.setString_("")
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def layout(self) -> None:
        bounds = self._content.bounds()
        layout = input_window_layout(
            float(bounds.size.width),
            float(bounds.size.height),
        )
        for view, frame in (
            (self._title, layout.title),
            (self._helper, layout.helper),
            (self._source_label, layout.source_label),
            (self._source_scroll, layout.source_editor),
            (self._result_label, layout.result_label),
            (self._result_scroll, layout.result_editor),
            (self._separator, layout.separator),
            (self._status, layout.status),
            (self._shortcut, layout.shortcut),
            (self._button, layout.button),
        ):
            _set_frame(view, frame)

    def _run(self, text: str) -> None:
        try:
            job = self._translate(text)
        except Exception as exc:
            job = TranslateJob(
                kind=JobKind.SELECTION,
                status=JobStatus.FAILURE,
                source_text=text,
                translated_text=None,
                error=str(exc),
            )
        self._apply_result(job)

    def _apply_result(self, job: TranslateJob) -> None:
        from Foundation import NSThread
        from PyObjCTools.AppHelper import callAfter

        if NSThread.isMainThread():
            self._show_result(job)
            return
        callAfter(self._show_result, job)

    def _show_result(self, job: TranslateJob) -> None:
        self._busy = False
        _style_primary_button(self._button, enabled=True)
        self._result.setString_(format_input_translation(job))
        self._result.scrollRangeToVisible_((0, 0))
        if job.status is JobStatus.SUCCESS:
            self._status.setStringValue_("")
        elif job.error == "empty_text":
            self._status.setStringValue_("请输入要翻译的文字。")
        else:
            self._status.setStringValue_("")


def _text_label(
    parent,
    title: str,
    *,
    font_size: float,
    color: str,
    weight: str = "regular",
    alignment: str = "left",
):
    from AppKit import NSMakeRect, NSTextAlignmentCenter, NSTextField

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 1.0, 1.0))
    label.setStringValue_(title)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setFont_(_system_font(font_size, weight))
    label.setTextColor_(_color(color))
    if alignment == "center":
        label.setAlignment_(NSTextAlignmentCenter)
    parent.addSubview_(label)
    return label


def _scrolling_text(
    parent,
    *,
    placeholder: str,
    editable: bool,
    accent_border: bool,
):
    from AppKit import (
        NSFontAttributeName,
        NSForegroundColorAttributeName,
        NSMakeRect,
        NSNoBorder,
        NSScrollView,
        NSTextView,
        NSView,
        NSViewHeightSizable,
        NSViewWidthSizable,
    )
    from Foundation import NSAttributedString

    wrapper = NSView.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 3.0, 3.0))
    wrapper.setWantsLayer_(True)
    wrapper_layer = wrapper.layer()
    if wrapper_layer is not None:
        wrapper_layer.setBackgroundColor_(_cg_color("#F7F8FC"))
        wrapper_layer.setCornerRadius_(10.0)
        wrapper_layer.setBorderWidth_(1.0)
        border = "#7778FF" if accent_border else "#DDE1EA"
        wrapper_layer.setBorderColor_(_cg_color(border))
        wrapper_layer.setMasksToBounds_(True)
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(1.0, 1.0, 1.0, 1.0))
    scroll.setHasVerticalScroller_(True)
    scroll.setHasHorizontalScroller_(False)
    scroll.setAutohidesScrollers_(True)
    scroll.setBorderType_(NSNoBorder)
    scroll.setDrawsBackground_(True)
    scroll.setBackgroundColor_(_color("#F7F8FC"))
    scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    text = NSTextView.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 1.0, 1.0))
    text.setRichText_(False)
    text.setEditable_(editable)
    text.setSelectable_(True)
    text.setAllowsUndo_(editable)
    text.setFont_(_system_font(15.0, "regular"))
    text.setTextColor_(_color("#1F2430"))
    text.setInsertionPointColor_(_color("#4F46E5"))
    text.setDrawsBackground_(True)
    text.setBackgroundColor_(_color("#F7F8FC"))
    text.setTextContainerInset_((14.0, 12.0))
    text.setVerticallyResizable_(True)
    text.setHorizontallyResizable_(False)
    text.setAutoresizingMask_(NSViewWidthSizable)
    text.setMinSize_((0.0, 0.0))
    text.setMaxSize_((1.0e7, 1.0e7))
    container = text.textContainer()
    container.setWidthTracksTextView_(True)
    container.setContainerSize_((1.0, 1.0e7))
    placeholder_value = NSAttributedString.alloc().initWithString_attributes_(
        placeholder,
        {
            NSFontAttributeName: _system_font(15.0, "regular"),
            NSForegroundColorAttributeName: _color("#A1A7B4"),
        },
    )
    text.setPlaceholderAttributedString_(placeholder_value)
    scroll.setDocumentView_(text)
    wrapper.addSubview_(scroll)
    parent.addSubview_(wrapper)
    return wrapper, text


def _system_font(size: float, weight: str):
    from AppKit import (
        NSFont,
        NSFontWeightMedium,
        NSFontWeightRegular,
        NSFontWeightSemibold,
    )

    weights = {
        "regular": NSFontWeightRegular,
        "medium": NSFontWeightMedium,
        "semibold": NSFontWeightSemibold,
    }
    return NSFont.systemFontOfSize_weight_(size, weights[weight])


def _color(value: str):
    from AppKit import NSColor

    red, green, blue = _color_components(value)
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 1.0)


def _cg_color(value: str):
    from Quartz import CGColorCreateGenericRGB

    red, green, blue = _color_components(value)
    return CGColorCreateGenericRGB(red, green, blue, 1.0)


def _color_components(value: str) -> tuple[float, float, float]:
    raw = value.removeprefix("#")
    if len(raw) != 6:
        raise ValueError("color must use six-digit hex notation")
    red, green, blue = (int(raw[index : index + 2], 16) for index in (0, 2, 4))
    return red / 255.0, green / 255.0, blue / 255.0


def _separator(parent):
    from AppKit import NSMakeRect, NSView

    separator = NSView.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 1.0, 1.0))
    separator.setWantsLayer_(True)
    layer = separator.layer()
    if layer is not None:
        layer.setBackgroundColor_(_cg_color("#E6E8EF"))
    parent.addSubview_(separator)
    return separator


def _style_primary_button(button: object, *, enabled: bool) -> None:
    from AppKit import NSFontAttributeName, NSForegroundColorAttributeName
    from Foundation import NSAttributedString

    button.setBordered_(False)
    button.setWantsLayer_(True)
    button.setEnabled_(enabled)
    layer = button.layer()
    if layer is not None:
        fill = "#4F46E5" if enabled else "#B9BBEA"
        layer.setBackgroundColor_(_cg_color(fill))
        layer.setCornerRadius_(9.0)
    title = NSAttributedString.alloc().initWithString_attributes_(
        INPUT_TRANSLATE_BUTTON,
        {
            NSFontAttributeName: _system_font(14.0, "semibold"),
            NSForegroundColorAttributeName: _color("#FFFFFF"),
        },
    )
    button.setAttributedTitle_(title)


def _style_window_content(window: object, content: object) -> None:
    background = _color("#FFFFFF")
    window.setBackgroundColor_(background)
    content.setWantsLayer_(True)
    layer = content.layer()
    if layer is not None:
        layer.setBackgroundColor_(_cg_color("#FFFFFF"))


def _set_frame(view: object, frame: InputFrame) -> None:
    from AppKit import NSMakeRect

    view.setFrame_(NSMakeRect(frame.x, frame.y, frame.width, frame.height))


def _prepare_input_window(window: object) -> None:
    from AppKit import (
        NSFloatingWindowLevel,
        NSWindowCollectionBehaviorMoveToActiveSpace,
    )

    window.setLevel_(NSFloatingWindowLevel)
    window.setReleasedWhenClosed_(False)
    window.setHidesOnDeactivate_(False)
    set_floating = getattr(window, "setFloatingPanel_", None)
    if callable(set_floating):
        set_floating(True)
    window.setCollectionBehavior_(NSWindowCollectionBehaviorMoveToActiveSpace)


def _input_controller_class() -> type:
    global _InputController
    if _InputController is not None:
        return _InputController
    from Foundation import NSObject

    class AITranslateInputController(NSObject):
        def translateInput_(self, _sender) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.request_translate()

        def windowDidResize_(self, _notification) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.layout()

    _InputController = AITranslateInputController
    return AITranslateInputController


_InputController = None
