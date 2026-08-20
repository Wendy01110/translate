from __future__ import annotations

from collections.abc import Callable

from ai_translate.core.models import JobStatus, ScreenRect, TranslateJob
from ai_translate.interfaces.overlay import (
    OverlayContent,
    _ERROR_TEXT,
    _footnote,
    _prepare_overlay_window,
    ensure_edit_menu,
)

LIVE_BAR_HEIGHT = 88.0
LIVE_GAP = 10.0
LIVE_MIN_WIDTH = 280.0


def format_live_overlay(job: TranslateJob) -> OverlayContent:
    source = job.source_text or job.ocr_text or ""
    translation = job.translated_text or ""
    if job.status is JobStatus.FAILURE and job.error:
        translation = _ERROR_TEXT.get(job.error, job.error)
        if job.error == "empty_ocr_text":
            translation = ""
    elif job.status is JobStatus.PARTIAL and job.error and not translation:
        translation = _ERROR_TEXT.get(job.error, job.error)
    title = "实时"
    footnote = _footnote(job)
    if footnote:
        title = f"{title} · {footnote}"
    return OverlayContent(
        title=title,
        source=source,
        translation=translation,
        footnote=footnote,
    )


def format_live_status(message: str) -> OverlayContent:
    return OverlayContent(title="实时", source="", translation=message, footnote="")


def rects_intersect(left: ScreenRect, right: ScreenRect) -> bool:
    a = left.canonical()
    b = right.canonical()
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


def live_overlay_rect(
    anchor: ScreenRect,
    *,
    screen: ScreenRect,
    bar_height: float = LIVE_BAR_HEIGHT,
    gap: float = LIVE_GAP,
    min_width: float = LIVE_MIN_WIDTH,
) -> ScreenRect:
    region = anchor.canonical()
    display = screen.canonical()
    width = min(max(region.width, min_width), display.width)
    x = region.x
    if x + width > display.x + display.width:
        x = display.x + display.width - width
    if x < display.x:
        x = display.x
    below = ScreenRect(x=x, y=region.y - gap - bar_height, width=width, height=bar_height)
    above = ScreenRect(
        x=x,
        y=region.y + region.height + gap,
        width=width,
        height=bar_height,
    )
    if below.y >= display.y and not rects_intersect(below, region):
        return below
    if above.y + above.height <= display.y + display.height and not rects_intersect(
        above, region
    ):
        return above
    if not rects_intersect(below, region):
        return below
    return above


def should_focus_live_overlay() -> bool:
    return False


def display_for_anchor(
    anchor: ScreenRect,
    screens: tuple[ScreenRect, ...],
    fallback: ScreenRect,
) -> ScreenRect:
    for screen in screens:
        if rects_intersect(screen, anchor):
            return screen
    return fallback


class LiveOverlayPresenter:
    def __init__(self, *, on_stop: Callable[[], None] | None = None) -> None:
        self._on_stop = on_stop
        self._impl: _LiveOverlayBackend | None = None
        self._anchor: ScreenRect | None = None

    def set_stop(self, on_stop: Callable[[], None] | None) -> None:
        self._on_stop = on_stop

    def set_anchor(self, rect: ScreenRect | None) -> None:
        self._anchor = rect
        if self._impl is not None:
            self._impl.set_anchor(rect)

    def show_status(self, message: str, source: str | None = None) -> None:
        del source
        self._backend().show(format_live_status(message))

    def show(self, job: TranslateJob) -> None:
        self._backend().show(format_live_overlay(job))

    def hide(self) -> None:
        if self._impl is not None:
            self._impl.hide()

    def _backend(self) -> _LiveOverlayBackend:
        if self._impl is None:
            self._impl = _LiveOverlayBackend(on_stop=self._invoke_stop)
            self._impl.set_anchor(self._anchor)
        return self._impl

    def _invoke_stop(self) -> None:
        callback = self._on_stop
        if callback is not None:
            callback()


class _LiveOverlayBackend:
    def __init__(self, *, on_stop: Callable[[], None] | None = None) -> None:
        from AppKit import (
            NSBackingStoreBuffered,
            NSColor,
            NSFont,
            NSMakeRect,
            NSPanel,
            NSTextField,
            NSViewHeightSizable,
            NSViewWidthSizable,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )

        self._on_stop = on_stop
        self._anchor: ScreenRect | None = None
        self._NSColor = NSColor
        self._NSFont = NSFont
        self._NSMakeRect = NSMakeRect
        self._NSPanel = NSPanel
        self._NSTextField = NSTextField
        self._width_sizable = NSViewWidthSizable
        self._height_sizable = NSViewHeightSizable
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
        self._closing = False

    def set_anchor(self, rect: ScreenRect | None) -> None:
        self._anchor = rect
        self._placed = False

    def hide(self) -> None:
        from Foundation import NSThread
        from PyObjCTools.AppHelper import callAfter

        if NSThread.isMainThread():
            self._hide_on_main()
            return
        callAfter(self._hide_on_main)

    def _hide_on_main(self) -> None:
        window = self._window
        if window is None:
            return
        self._closing = True
        window.orderOut_(None)
        self._closing = False

    def show(self, content: OverlayContent) -> None:
        from Foundation import NSThread
        from PyObjCTools.AppHelper import callAfter

        if NSThread.isMainThread():
            self._show_on_main(content)
            return
        callAfter(self._show_on_main, content)

    def _show_on_main(self, content: OverlayContent) -> None:
        if self._window is None:
            self._build_window()
        self._window.setTitle_(content.title)
        self._source.setStringValue_(content.source or "")
        self._translation.setStringValue_(content.translation or "")
        _prepare_overlay_window(self._window)
        if not self._placed:
            self._place_window()
            self._placed = True
        if should_focus_live_overlay():
            self._window.makeKeyAndOrderFront_(None)
        self._window.orderFrontRegardless()

    def _place_window(self) -> None:
        from AppKit import NSScreen

        window = self._window
        screens = tuple(
            _ns_frame_to_rect(screen.frame()) for screen in (NSScreen.screens() or [])
        )
        main = NSScreen.mainScreen()
        fallback = (
            _ns_frame_to_rect(main.frame())
            if main is not None
            else ScreenRect(x=0.0, y=0.0, width=1440.0, height=900.0)
        )
        if not screens:
            screens = (fallback,)
        anchor = self._anchor or ScreenRect(
            x=fallback.x + 80.0,
            y=fallback.y + 80.0,
            width=480.0,
            height=80.0,
        )
        display = display_for_anchor(anchor, screens, fallback)
        placed = live_overlay_rect(anchor, screen=display)
        window.setFrame_display_(((placed.x, placed.y), (placed.width, placed.height)), True)

    def _build_window(self) -> None:
        window = self._NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            self._NSMakeRect(0.0, 0.0, 520.0, LIVE_BAR_HEIGHT),
            self._style,
            self._backing,
            False,
        )
        window.setMinSize_((LIVE_MIN_WIDTH, 64.0))
        ensure_edit_menu()
        _prepare_overlay_window(window)
        delegate = _live_window_delegate_class().alloc().init()
        delegate.owner = self
        window.setDelegate_(delegate)
        content = window.contentView()
        bounds = content.bounds()
        width = bounds.size.width
        height = bounds.size.height
        translation = self._NSTextField.alloc().initWithFrame_(
            self._NSMakeRect(12.0, 28.0, width - 24.0, height - 36.0)
        )
        translation.setBezeled_(False)
        translation.setDrawsBackground_(False)
        translation.setEditable_(False)
        translation.setSelectable_(True)
        translation.setFont_(self._NSFont.systemFontOfSize_(16.0))
        translation.setAutoresizingMask_(self._width_sizable | self._height_sizable)
        source = self._NSTextField.alloc().initWithFrame_(
            self._NSMakeRect(12.0, 8.0, width - 24.0, 18.0)
        )
        source.setBezeled_(False)
        source.setDrawsBackground_(False)
        source.setEditable_(False)
        source.setSelectable_(True)
        source.setFont_(self._NSFont.systemFontOfSize_(11.0))
        source.setTextColor_(self._NSColor.secondaryLabelColor())
        source.setAutoresizingMask_(self._width_sizable)
        content.addSubview_(translation)
        content.addSubview_(source)
        self._window = window
        self._source = source
        self._translation = translation
        self._delegate = delegate

    def handle_close(self) -> bool:
        if self._closing:
            return True
        callback = self._on_stop
        if callback is not None:
            callback()
        return True


def _live_window_delegate_class() -> type:
    global _LiveWindowDelegate
    if _LiveWindowDelegate is not None:
        return _LiveWindowDelegate
    from Foundation import NSObject
    import objc

    class AITranslateLiveOverlayDelegate(NSObject):
        def windowShouldClose_(self, _window) -> bool:
            owner = getattr(self, "owner", None)
            if owner is not None:
                return bool(owner.handle_close())
            return True

    _LiveWindowDelegate = AITranslateLiveOverlayDelegate
    return AITranslateLiveOverlayDelegate


_LiveWindowDelegate = None


def _ns_frame_to_rect(frame: object) -> ScreenRect:
    origin = frame.origin
    size = frame.size
    return ScreenRect(
        x=float(origin.x),
        y=float(origin.y),
        width=float(size.width),
        height=float(size.height),
    )
