from __future__ import annotations

from dataclasses import dataclass

from ai_translate.core.models import JobKind, JobStatus, TranslateJob


@dataclass(frozen=True)
class OverlayContent:
    title: str
    source: str
    translation: str
    footnote: str


_ERROR_TEXT = {
    "accessibility_required": (
        "未开启辅助功能，无法读取选区。\n"
        "请打开：系统设置 → 隐私与安全性 → 辅助功能 → AI Translate。"
    ),
    "empty_text": "没有读到选中的文字。请先选中，或先 Command+C 再按热键。",
    "copy_simulation_failed": "无法模拟复制。请检查辅助功能权限。",
    "clipboard_read_failed": "无法读取剪贴板。",
    "clipboard_write_failed": "无法写入剪贴板。",
    "selection_too_long": "选中的文字太长。",
    "text_too_long": "文字太长。",
    "unsupported_language": "当前翻译源不支持这个语言。",
    "http_403": "网页翻译被拒绝，可稍后再试或改用官方密钥源。",
    "http_429": "翻译请求太频繁，请稍后再试。",
    "translate_not_configured": "翻译模型未配置。",
    "screenshot_cancelled": "已取消圈选。",
}


def format_overlay(job: TranslateJob) -> OverlayContent:
    title = "OCR" if job.kind is JobKind.OCR else "划词"
    if job.error == "accessibility_required":
        title = "需要权限"
    elif job.status is JobStatus.FAILURE:
        title = f"{title}失败"
    source = job.source_text or job.ocr_text or ""
    translation = job.translated_text or ""
    if job.status is JobStatus.FAILURE and job.error:
        translation = _ERROR_TEXT.get(job.error, job.error)
    elif job.status is JobStatus.PARTIAL and job.error and not translation:
        translation = _ERROR_TEXT.get(job.error, job.error)
    footnote = _footnote(job)
    return OverlayContent(
        title=title,
        source=source,
        translation=translation,
        footnote=footnote,
    )


def format_status(message: str, source: str = "") -> OverlayContent:
    return OverlayContent(title="翻译", source=source, translation=message, footnote="")


def should_center_overlay(*, created: bool) -> bool:
    return created


def should_focus_overlay(*, visible: bool) -> bool:
    return not visible


class StdoutPresenter:
    def show_status(self, message: str, source: str | None = None) -> None:
        return None

    def show(self, job: TranslateJob) -> None:
        content = format_overlay(job)
        print(f"{content.title}\n{content.source}\n\n{content.translation}")


class OverlayPresenter:
    def __init__(self) -> None:
        self._impl = _build_backend()

    def show_status(self, message: str, source: str | None = None) -> None:
        self._impl.show(format_status(message, source=source or ""))

    def show(self, job: TranslateJob) -> None:
        self._impl.show(format_overlay(job))


class _AppleScriptBackend:
    def show(self, content: OverlayContent) -> None:
        import subprocess

        body = "\n\n".join(part for part in (content.source, content.translation) if part)
        script = (
            f"display dialog {_applescript_string(body or content.title)} "
            f"with title {_applescript_string(content.title)} "
            'buttons {"OK"} default button "OK" giving up after 45'
        )
        subprocess.run(["osascript", "-e", script], check=False, timeout=60)


class _AppKitBackend:
    def __init__(self) -> None:
        from AppKit import (
            NSApplication,
            NSBackingStoreBuffered,
            NSBezelBorder,
            NSColor,
            NSFont,
            NSMakeRect,
            NSPanel,
            NSScrollView,
            NSSplitView,
            NSTextField,
            NSTextView,
            NSView,
            NSViewHeightSizable,
            NSViewMinYMargin,
            NSViewWidthSizable,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )

        self._NSColor = NSColor
        self._NSFont = NSFont
        self._NSMakeRect = NSMakeRect
        self._NSPanel = NSPanel
        self._NSScrollView = NSScrollView
        self._NSSplitView = NSSplitView
        self._NSTextField = NSTextField
        self._NSTextView = NSTextView
        self._NSView = NSView
        self._NSBezelBorder = NSBezelBorder
        self._width_sizable = NSViewWidthSizable
        self._height_sizable = NSViewHeightSizable
        self._min_y_margin = NSViewMinYMargin
        self._style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable
        )
        self._backing = NSBackingStoreBuffered
        self._window = None
        self._source = None
        self._translation = None
        self._placed = False
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(1)

    def show(self, content: OverlayContent) -> None:
        from Foundation import NSThread
        from PyObjCTools.AppHelper import callAfter

        if NSThread.isMainThread():
            self._show_on_main(content)
            return
        callAfter(self._show_on_main, content)

    def _show_on_main(self, content: OverlayContent) -> None:
        from AppKit import NSApp

        created = self._window is None
        if created:
            self._build_window()
        title = content.title
        if content.footnote:
            title = f"{title} · {content.footnote}"
        self._window.setTitle_(title)
        _set_scrollable_text(self._source, content.source)
        _set_scrollable_text(self._translation, content.translation)
        _prepare_overlay_window(self._window)
        visible = bool(self._window.isVisible())
        if should_center_overlay(created=created) and not self._placed:
            self._window.center()
            self._placed = True
        if should_focus_overlay(visible=visible):
            NSApp.activateIgnoringOtherApps_(True)
            self._window.makeKeyAndOrderFront_(None)
        self._window.orderFrontRegardless()

    def _build_window(self) -> None:
        window = self._NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            self._NSMakeRect(0.0, 0.0, 520.0, 460.0),
            self._style,
            self._backing,
            False,
        )
        window.setMinSize_((360.0, 300.0))
        _prepare_overlay_window(window)
        content = window.contentView()
        bounds = content.bounds()
        split = self._NSSplitView.alloc().initWithFrame_(bounds)
        split.setVertical_(False)
        split.setDividerStyle_(1)
        split.setAutoresizingMask_(self._width_sizable | self._height_sizable)
        source_pane, source = self._pane("原文", bounds.size.width, 200.0)
        translation_pane, translation = self._pane(
            "译文",
            bounds.size.width,
            200.0,
        )
        split.addSubview_(source_pane)
        split.addSubview_(translation_pane)
        content.addSubview_(split)
        self._window = window
        self._source = source
        self._translation = translation

    def _pane(self, title: str, width: float, height: float):
        view = self._NSView.alloc().initWithFrame_(
            self._NSMakeRect(0.0, 0.0, width, height)
        )
        label = self._label(title, 10, height - 24, width - 20, 16)
        label.setAutoresizingMask_(self._width_sizable | self._min_y_margin)
        scroll, text = self._scrolling_text(10, 8, width - 20, height - 34)
        scroll.setAutoresizingMask_(self._width_sizable | self._height_sizable)
        view.addSubview_(label)
        view.addSubview_(scroll)
        return view, text

    def _label(self, text: str, x: float, y: float, w: float, h: float):
        field = self._NSTextField.alloc().initWithFrame_(self._NSMakeRect(x, y, w, h))
        field.setStringValue_(text)
        field.setBezeled_(False)
        field.setDrawsBackground_(False)
        field.setEditable_(False)
        field.setSelectable_(False)
        field.setFont_(self._NSFont.systemFontOfSize_(11.0))
        field.setTextColor_(self._NSColor.secondaryLabelColor())
        return field

    def _scrolling_text(self, x: float, y: float, w: float, h: float):
        scroll = self._NSScrollView.alloc().initWithFrame_(
            self._NSMakeRect(x, y, w, h)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setHasHorizontalScroller_(False)
        scroll.setAutohidesScrollers_(True)
        scroll.setBorderType_(self._NSBezelBorder)
        text = self._NSTextView.alloc().initWithFrame_(self._NSMakeRect(0.0, 0.0, w, h))
        text.setEditable_(False)
        text.setSelectable_(True)
        text.setRichText_(False)
        text.setFont_(self._NSFont.systemFontOfSize_(14.0))
        text.setVerticallyResizable_(True)
        text.setHorizontallyResizable_(False)
        text.setAutoresizingMask_(self._width_sizable)
        text.setMinSize_((0.0, 0.0))
        text.setMaxSize_((1.0e7, 1.0e7))
        container = text.textContainer()
        container.setWidthTracksTextView_(True)
        container.setContainerSize_((w, 1.0e7))
        scroll.setDocumentView_(text)
        return scroll, text


def _set_scrollable_text(view: object, value: str) -> None:
    view.setString_(value or "")
    view.scrollRangeToVisible_((0, 0))


def _prepare_overlay_window(window: object) -> None:
    from AppKit import (
        NSFloatingWindowLevel,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
    )

    window.setLevel_(NSFloatingWindowLevel)
    window.setReleasedWhenClosed_(False)
    window.setHidesOnDeactivate_(False)
    window.setFloatingPanel_(True)
    window.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )


def _footnote(job: TranslateJob) -> str:
    if job.kind is JobKind.OCR and job.ocr_engine == "vision":
        return "本机"
    if job.kind is JobKind.OCR and job.ocr_engine == "model":
        return "模型"
    labels = {
        "google_web": "Google 内置",
        "bing_web": "Bing 内置",
        "deepl_web": "DeepL 内置",
        "deepl": "DeepL",
        "microsoft": "Microsoft",
        "google": "Google",
    }
    if job.translate_model in labels:
        return labels[job.translate_model]
    return ""


def _build_backend() -> _AppleScriptBackend | _AppKitBackend:
    try:
        import AppKit  # noqa: F401
        from PyObjCTools.AppHelper import callAfter  # noqa: F401

        return _AppKitBackend()
    except Exception:
        return _AppleScriptBackend()


def _applescript_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
