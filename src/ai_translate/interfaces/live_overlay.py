from __future__ import annotations

from collections.abc import Callable
from math import ceil

from ai_translate.core.models import JobStatus, ScreenRect, TranslateJob
from ai_translate.interfaces.overlay import (
    OverlayContent,
    _ERROR_TEXT,
    _footnote,
    _overlay_color,
    _overlay_scrolling_text,
    _prepare_overlay_window,
    _set_scrollable_text,
    _style_overlay_window_content,
    ensure_edit_menu,
)

LIVE_BAR_HEIGHT = 112.0
LIVE_MAX_HEIGHT = 240.0
LIVE_GAP = 10.0
LIVE_MIN_WIDTH = 280.0
_TEXT_MARGIN = 8.0
_TEXT_GAP = 6.0
_TRANSLATION_MIN_HEIGHT = 28.0
_SOURCE_MAX_HEIGHT = 40.0


def live_overlay_height(
    translation_height: float,
    source_height: float,
    *,
    chrome_height: float,
) -> float:
    source = min(source_height, _SOURCE_MAX_HEIGHT)
    requested = (
        chrome_height
        + 2 * _TEXT_MARGIN
        + max(translation_height, _TRANSLATION_MIN_HEIGHT)
        + source
        + (_TEXT_GAP if source else 0)
    )
    return min(max(requested, LIVE_BAR_HEIGHT), LIVE_MAX_HEIGHT)


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
    bar_width: float | None = None,
    gap: float = LIVE_GAP,
    min_width: float = LIVE_MIN_WIDTH,
) -> ScreenRect:
    region = anchor.canonical()
    display = screen.canonical()
    preferred_width = region.width if bar_width is None else bar_width
    width = min(max(preferred_width, min_width), display.width)
    below_space = max(0.0, region.y - display.y - gap)
    above_space = max(0.0, display.y + display.height - region.y - region.height - gap)
    if bar_height > max(below_space, above_space):
        available = max(below_space, above_space)
        if available >= min(LIVE_BAR_HEIGHT, bar_height):
            bar_height = available
        else:
            side_height = min(bar_height, display.height)
            side_y = min(max(region.y, display.y), display.y + display.height - side_height)
            right_space = display.x + display.width - region.x - region.width - gap
            left_space = region.x - display.x - gap
            if right_space >= min_width:
                return ScreenRect(
                    x=region.x + region.width + gap,
                    y=side_y,
                    width=min(width, right_space),
                    height=side_height,
                )
            if left_space >= min_width:
                side_width = min(width, left_space)
                return ScreenRect(
                    x=region.x - gap - side_width,
                    y=side_y,
                    width=side_width,
                    height=side_height,
                )
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
            NSFont,
            NSMakeRect,
            NSPanel,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )

        self._on_stop = on_stop
        self._anchor: ScreenRect | None = None
        self._NSFont = NSFont
        self._NSMakeRect = NSMakeRect
        self._NSPanel = NSPanel
        self._style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskResizable
        )
        self._backing = NSBackingStoreBuffered
        self._window = None
        self._source = None
        self._translation = None
        self._source_area = None
        self._translation_area = None
        self._placed = False
        self._closing = False
        self._laying_out = False

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
        _set_scrollable_text(self._source, content.source)
        _set_scrollable_text(self._translation, content.translation)
        _prepare_overlay_window(self._window, pinned=True)
        self.layout_window()
        if should_focus_live_overlay():
            self._window.makeKeyAndOrderFront_(None)
        self._window.orderFrontRegardless()

    def layout_window(self) -> None:
        if self._laying_out or self._window is None or self._translation is None:
            return
        self._laying_out = True
        try:
            self._layout_window()
        finally:
            self._laying_out = False

    def _layout_window(self) -> None:
        from AppKit import NSScreen

        window = self._window
        screens = tuple(
            _ns_frame_to_rect(screen.visibleFrame()) for screen in (NSScreen.screens() or [])
        )
        main = NSScreen.mainScreen()
        fallback = (
            _ns_frame_to_rect(main.visibleFrame())
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
        window.setMinSize_(
            (min(LIVE_MIN_WIDTH, display.width), min(LIVE_BAR_HEIGHT, display.height))
        )
        window.setMaxSize_((display.width, min(LIVE_MAX_HEIGHT, display.height)))
        base = live_overlay_rect(
            anchor,
            screen=display,
            bar_width=float(window.frame().size.width) if self._placed else None,
        )
        width = base.width - 2 * _TEXT_MARGIN
        for area in (self._source_area, self._translation_area):
            area.setFrame_(
                self._NSMakeRect(_TEXT_MARGIN, _TEXT_MARGIN, width, _TRANSLATION_MIN_HEIGHT)
            )
        source_height = self._text_height(self._source) if self._source.string() else 0.0
        chrome_height = window.frame().size.height - window.contentView().bounds().size.height
        height = live_overlay_height(
            self._text_height(self._translation),
            source_height,
            chrome_height=chrome_height,
        )
        placed = live_overlay_rect(
            anchor, screen=display, bar_width=base.width, bar_height=height
        )
        window.setFrame_display_(((placed.x, placed.y), (placed.width, placed.height)), True)
        self._placed = True
        bounds = window.contentView().bounds().size
        source_height = min(
            source_height,
            _SOURCE_MAX_HEIGHT,
            max(0.0, bounds.height - 2 * _TEXT_MARGIN - _TEXT_GAP - _TRANSLATION_MIN_HEIGHT),
        )
        self._source_area.setHidden_(not self._source.string())
        self._source_area.setFrame_(
            self._NSMakeRect(
                _TEXT_MARGIN, _TEXT_MARGIN, bounds.width - 2 * _TEXT_MARGIN, source_height
            )
        )
        y = _TEXT_MARGIN + source_height + (_TEXT_GAP if source_height else 0.0)
        self._translation_area.setFrame_(
            self._NSMakeRect(
                _TEXT_MARGIN,
                y,
                bounds.width - 2 * _TEXT_MARGIN,
                bounds.height - y - _TEXT_MARGIN,
            )
        )

    @staticmethod
    def _text_height(view: object) -> float:
        container = view.textContainer()
        manager = view.layoutManager()
        manager.ensureLayoutForTextContainer_(container)
        scroll = view.enclosingScrollView()
        border_height = scroll.superview().bounds().size.height - scroll.contentSize().height
        return ceil(
            manager.usedRectForTextContainer_(container).size.height
            + 2 * view.textContainerInset().height
            + border_height
        )

    def _build_window(self) -> None:
        window = self._NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            self._NSMakeRect(0.0, 0.0, 520.0, LIVE_BAR_HEIGHT),
            self._style,
            self._backing,
            False,
        )
        ensure_edit_menu()
        _prepare_overlay_window(window, pinned=True)
        delegate = _live_window_delegate_class().alloc().init()
        delegate.owner = self
        window.setDelegate_(delegate)
        content = window.contentView()
        _style_overlay_window_content(window, content)
        translation_area, translation = _overlay_scrolling_text(
            content, accent_border=False, editable=False
        )
        translation.setFont_(self._NSFont.systemFontOfSize_(16.0))
        source_area, source = _overlay_scrolling_text(
            content, accent_border=False, editable=False
        )
        source.setFont_(self._NSFont.systemFontOfSize_(11.0))
        source.setTextColor_(_overlay_color("#73798B"))
        for area, text, hint in (
            (translation_area, translation, "滚动查看完整译文"),
            (source_area, source, "滚动查看完整原文"),
        ):
            text.setTextContainerInset_((4.0, 2.0))
            area.setToolTip_(hint)
        self._window = window
        self._source = source
        self._translation = translation
        self._source_area = source_area
        self._translation_area = translation_area
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
        def windowDidResize_(self, _notification) -> None:
            owner = getattr(self, "owner", None)
            if owner is not None:
                owner.layout_window()

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
