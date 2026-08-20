from __future__ import annotations

from collections.abc import Callable

from ai_translate.core.models import ScreenRect


def rect_from_drag(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> ScreenRect:
    return ScreenRect(
        x=start_x,
        y=start_y,
        width=end_x - start_x,
        height=end_y - start_y,
    ).canonical()


class RegionPicker:
    needs_main_thread = True

    def __init__(self) -> None:
        self._session: _PickerSession | None = None

    def __call__(self) -> ScreenRect | None:
        return pick_screen_region()

    def start(self, on_complete: Callable[[ScreenRect | None], None]) -> None:
        if self._session is not None:
            on_complete(None)
            return

        def finish(rect: ScreenRect | None) -> None:
            self._session = None
            on_complete(rect)

        session = _PickerSession(on_complete=finish)
        self._session = session
        try:
            session.begin()
        except Exception:
            self._session = None
            raise

    def cancel(self) -> None:
        session = self._session
        if session is None:
            return
        try:
            from Foundation import NSThread
            from PyObjCTools.AppHelper import callAfter
        except Exception:
            session.complete(None)
            return
        if NSThread.isMainThread():
            session.complete(None)
            return
        callAfter(session.complete, None)


def pick_screen_region() -> ScreenRect | None:
    session = _PickerSession()
    session.begin()
    return session.run_modal()


class _PickerSession:
    def __init__(
        self,
        *,
        on_complete: Callable[[ScreenRect | None], None] | None = None,
    ) -> None:
        self.finished = False
        self.rect: ScreenRect | None = None
        self._on_complete = on_complete
        self._window = None
        self._view = None
        self._modal = False

    def begin(self) -> None:
        from AppKit import (
            NSApplication,
            NSBackingStoreBuffered,
            NSBorderlessWindowMask,
            NSColor,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
        )

        frame = _union_screen_frame()
        window = (
            _picker_panel_class()
            .alloc()
            .initWithContentRect_styleMask_backing_defer_(
                frame,
                NSBorderlessWindowMask,
                NSBackingStoreBuffered,
                False,
            )
        )
        window.setLevel_(1024)
        window.setOpaque_(False)
        window.setBackgroundColor_(NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.18))
        window.setIgnoresMouseEvents_(False)
        window.setAcceptsMouseMovedEvents_(True)
        window.setReleasedWhenClosed_(False)
        window.setHidesOnDeactivate_(False)
        window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        view = (
            _picker_view_class()
            .alloc()
            .initWithFrame_(window.contentView().bounds())
        )
        view.session = self
        view.setAutoresizingMask_(18)
        window.setContentView_(view)
        app = NSApplication.sharedApplication()
        app.activateIgnoringOtherApps_(True)
        window.makeKeyAndOrderFront_(None)
        window.makeFirstResponder_(view)
        window.orderFrontRegardless()
        self._window = window
        self._view = view

    def run_modal(self) -> ScreenRect | None:
        from AppKit import NSApp

        window = self._window
        if window is None:
            return None
        self._modal = True
        try:
            NSApp.runModalForWindow_(window)
        finally:
            self._modal = False
        return self.rect

    def complete(self, rect: ScreenRect | None) -> None:
        if self.finished:
            return
        if rect is not None:
            rect = rect.canonical()
            if not rect.is_usable():
                rect = None
        self.rect = rect
        self.finished = True
        if self._modal:
            from AppKit import NSApp

            NSApp.stopModal()
        window = self._window
        view = self._view
        self._window = None
        self._view = None
        if view is not None:
            view.session = None
        if window is not None:
            window.orderOut_(None)
        callback = self._on_complete
        self._on_complete = None
        if callback is not None:
            callback(rect)


def _union_screen_frame():
    from AppKit import NSMakeRect, NSScreen

    screens = list(NSScreen.screens() or [])
    if not screens:
        return NSMakeRect(0.0, 0.0, 1440.0, 900.0)
    frame = screens[0].frame()
    min_x = float(frame.origin.x)
    min_y = float(frame.origin.y)
    max_x = min_x + float(frame.size.width)
    max_y = min_y + float(frame.size.height)
    for screen in screens[1:]:
        item = screen.frame()
        x = float(item.origin.x)
        y = float(item.origin.y)
        max_x = max(max_x, x + float(item.size.width))
        max_y = max(max_y, y + float(item.size.height))
        min_x = min(min_x, x)
        min_y = min(min_y, y)
    return NSMakeRect(min_x, min_y, max_x - min_x, max_y - min_y)


def _picker_panel_class() -> type:
    global _PickerPanel
    if _PickerPanel is not None:
        return _PickerPanel
    from AppKit import NSPanel

    class AITranslateRegionPickerPanel(NSPanel):
        def canBecomeKeyWindow(self) -> bool:
            return True

        def canBecomeMainWindow(self) -> bool:
            return True

    _PickerPanel = AITranslateRegionPickerPanel
    return AITranslateRegionPickerPanel


def _picker_view_class() -> type:
    global _PickerView
    if _PickerView is not None:
        return _PickerView
    from AppKit import NSBezierPath, NSColor, NSView
    import objc

    class AITranslateRegionPickerView(NSView):
        def initWithFrame_(self, frame):
            self = objc.super(AITranslateRegionPickerView, self).initWithFrame_(frame)
            if self is None:
                return None
            self.session = None
            self.dragging = False
            self.start_x = 0.0
            self.start_y = 0.0
            self.current_x = 0.0
            self.current_y = 0.0
            return self

        def acceptsFirstResponder(self) -> bool:
            return True

        def mouseDown_(self, event) -> None:
            point = self._screen_point(event)
            self.dragging = True
            self.start_x = point[0]
            self.start_y = point[1]
            self.current_x = point[0]
            self.current_y = point[1]
            self.setNeedsDisplay_(True)

        def mouseDragged_(self, event) -> None:
            if not self.dragging:
                return
            point = self._screen_point(event)
            self.current_x = point[0]
            self.current_y = point[1]
            self.setNeedsDisplay_(True)

        def mouseUp_(self, event) -> None:
            if not self.dragging:
                return
            point = self._screen_point(event)
            session = self.session
            if session is not None:
                session.complete(
                    rect_from_drag(
                        self.start_x,
                        self.start_y,
                        point[0],
                        point[1],
                    )
                )
            self.dragging = False

        def keyDown_(self, event) -> None:
            if int(event.keyCode()) == 53:
                session = self.session
                if session is not None:
                    session.complete(None)
                return
            objc.super(AITranslateRegionPickerView, self).keyDown_(event)

        def drawRect_(self, _rect) -> None:
            if not self.dragging:
                return
            window = self.window()
            if window is None:
                return
            local_start = window.convertPointFromScreen_((self.start_x, self.start_y))
            local_end = window.convertPointFromScreen_((self.current_x, self.current_y))
            x = min(local_start.x, local_end.x)
            y = min(local_start.y, local_end.y)
            width = abs(local_end.x - local_start.x)
            height = abs(local_end.y - local_start.y)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.2, 0.55, 1.0, 0.18
            ).setFill()
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.2, 0.55, 1.0, 0.95
            ).setStroke()
            path = NSBezierPath.bezierPathWithRect_(((x, y), (width, height)))
            path.setLineWidth_(2.0)
            path.fill()
            path.stroke()

        def _screen_point(self, event) -> tuple[float, float]:
            window = self.window()
            local = event.locationInWindow()
            if window is None:
                return (float(local.x), float(local.y))
            screen = window.convertPointToScreen_(local)
            return (float(screen.x), float(screen.y))

    _PickerView = AITranslateRegionPickerView
    return AITranslateRegionPickerView


_PickerView = None
_PickerPanel = None
