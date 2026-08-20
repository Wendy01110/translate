from __future__ import annotations

import threading
from collections.abc import Callable

from ai_translate.core.models import JobKind, JobStatus, TranslateJob

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
            NSFont,
            NSMakeRect,
            NSTextField,
            NSWindow,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )

        self._translate = translate
        self._busy = False
        self._width = 520.0
        self._height = 480.0
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0.0, 0.0, self._width, self._height),
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("输入翻译")
        window.setMinSize_((400.0, 360.0))
        _prepare_input_window(window)
        content = window.contentView()
        if content is None:
            raise RuntimeError("input window has no content view")
        controller = _input_controller_class().alloc().init()
        controller.owner = self
        source_label = _label(content, "原文", 16.0, 444.0, 200.0)
        source_scroll, source = _scrolling_text(content, 16.0, 268.0, 488.0, 172.0)
        source.setEditable_(True)
        button = NSButton.alloc().initWithFrame_(NSMakeRect(414.0, 230.0, 90.0, 28.0))
        button.setTitle_("翻译")
        button.setBezelStyle_(1)
        button.setTarget_(controller)
        button.setAction_("translateInput:")
        button.setKeyEquivalent_("\r")
        button.setKeyEquivalentModifierMask_(NSEventModifierFlagCommand)
        result_label = _label(content, "译文", 16.0, 206.0, 200.0)
        result_scroll, result = _scrolling_text(content, 16.0, 48.0, 488.0, 154.0)
        result.setEditable_(False)
        status = NSTextField.alloc().initWithFrame_(NSMakeRect(16.0, 16.0, 488.0, 22.0))
        status.setBezeled_(False)
        status.setDrawsBackground_(False)
        status.setEditable_(False)
        status.setSelectable_(False)
        status.setFont_(NSFont.systemFontOfSize_(11.0))
        content.addSubview_(button)
        content.addSubview_(status)
        source_scroll.setAutoresizingMask_(18)
        result_scroll.setAutoresizingMask_(18)
        button.setAutoresizingMask_(8)
        source_label.setAutoresizingMask_(8)
        result_label.setAutoresizingMask_(8)
        status.setAutoresizingMask_(8)
        self._window = window
        self._controller = controller
        self._source = source
        self._result = result
        self._status = status
        self._button = button

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
        self._button.setEnabled_(False)
        self._status.setStringValue_("翻译中…")
        self._result.setString_("")
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

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
        self._button.setEnabled_(True)
        self._result.setString_(format_input_translation(job))
        self._result.scrollRangeToVisible_((0, 0))
        if job.status is JobStatus.SUCCESS:
            self._status.setStringValue_("")
        elif job.error == "empty_text":
            self._status.setStringValue_("请输入要翻译的文字。")
        else:
            self._status.setStringValue_("")


def _label(parent, title: str, x: float, y: float, width: float):
    from AppKit import NSMakeRect, NSTextField

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, 16.0))
    label.setStringValue_(title)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    parent.addSubview_(label)
    return label


def _scrolling_text(parent, x: float, y: float, w: float, h: float):
    from AppKit import (
        NSBezelBorder,
        NSFont,
        NSMakeRect,
        NSScrollView,
        NSTextView,
        NSViewWidthSizable,
    )

    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    scroll.setHasVerticalScroller_(True)
    scroll.setHasHorizontalScroller_(False)
    scroll.setAutohidesScrollers_(True)
    scroll.setBorderType_(NSBezelBorder)
    text = NSTextView.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, w, h))
    text.setRichText_(False)
    text.setFont_(NSFont.systemFontOfSize_(14.0))
    text.setVerticallyResizable_(True)
    text.setHorizontallyResizable_(False)
    text.setAutoresizingMask_(NSViewWidthSizable)
    text.setMinSize_((0.0, 0.0))
    text.setMaxSize_((1.0e7, 1.0e7))
    container = text.textContainer()
    container.setWidthTracksTextView_(True)
    container.setContainerSize_((w, 1.0e7))
    scroll.setDocumentView_(text)
    parent.addSubview_(scroll)
    return scroll, text


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

    _InputController = AITranslateInputController
    return AITranslateInputController


_InputController = None
