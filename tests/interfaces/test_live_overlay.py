import sys
from types import SimpleNamespace

import pytest

import ai_translate.interfaces.live_overlay as live_overlay_module
import ai_translate.interfaces.region_picker as region_picker_module
from ai_translate.core.models import JobKind, JobStatus, ScreenRect, TranslateJob
from ai_translate.interfaces.live_overlay import (
    LIVE_BAR_HEIGHT,
    display_for_anchor,
    format_live_overlay,
    live_overlay_rect,
    rects_intersect,
    should_focus_live_overlay,
)
from ai_translate.interfaces.region_picker import rect_from_drag


def test_live_overlay_places_below_region_without_overlap() -> None:
    screen = ScreenRect(x=0, y=0, width=1000, height=800)
    anchor = ScreenRect(x=100, y=200, width=400, height=60)
    placed = live_overlay_rect(anchor, screen=screen, bar_height=80, gap=10)
    assert placed.y + placed.height <= anchor.y
    assert not rects_intersect(placed, anchor)


def test_live_overlay_places_above_when_below_does_not_fit() -> None:
    screen = ScreenRect(x=0, y=0, width=1000, height=800)
    anchor = ScreenRect(x=100, y=20, width=400, height=60)
    placed = live_overlay_rect(anchor, screen=screen, bar_height=80, gap=10)
    assert placed.y >= anchor.y + anchor.height
    assert not rects_intersect(placed, anchor)


def test_live_overlay_height_includes_chrome_and_limits_source_space() -> None:
    height = live_overlay_module.live_overlay_height(120, 18, chrome_height=32)
    assert height == 192
    assert live_overlay_module.live_overlay_height(120, 18, chrome_height=42) == height + 10
    assert live_overlay_module.live_overlay_height(120, 2000, chrome_height=32) == 214


def test_live_overlay_height_is_bounded_for_short_and_long_text() -> None:
    assert live_overlay_module.live_overlay_height(20, 0, chrome_height=32) == LIVE_BAR_HEIGHT
    assert live_overlay_module.live_overlay_height(10000, 10000, chrome_height=32) == 240


@pytest.mark.parametrize(
    ("screen", "anchor"),
    [
        (ScreenRect(0, 0, 640, 180), ScreenRect(80, 20, 280, 30)),
        (ScreenRect(0, 0, 800, 300), ScreenRect(80, 180, 280, 60)),
        (ScreenRect(0, 0, 1000, 800), ScreenRect(80, 20, 300, 740)),
        (ScreenRect(0, 0, 1000, 800), ScreenRect(700, 20, 220, 740)),
        (ScreenRect(-1000, -800, 800, 600), ScreenRect(-920, -750, 300, 50)),
    ],
)
def test_live_overlay_adapts_to_free_screen_space_without_overlap(screen, anchor) -> None:
    placed = live_overlay_rect(anchor, screen=screen, bar_height=240)

    assert not rects_intersect(placed, anchor)
    assert screen.x <= placed.x
    assert placed.x + placed.width <= screen.x + screen.width
    assert screen.y <= placed.y
    assert placed.y + placed.height <= screen.y + screen.height
    assert LIVE_BAR_HEIGHT <= placed.height <= 240


def test_live_overlay_uses_resized_width_and_keeps_full_screen_region_outside() -> None:
    screen = ScreenRect(0, 0, 1000, 800)
    anchor = ScreenRect(80, 200, 700, 60)
    placed = live_overlay_rect(anchor, screen=screen, bar_width=300)
    assert placed.width == 300
    assert not rects_intersect(live_overlay_rect(screen, screen=screen), screen)


def test_live_overlay_does_not_steal_focus() -> None:
    assert should_focus_live_overlay() is False


def test_display_for_anchor_prefers_intersecting_screen() -> None:
    left = ScreenRect(x=0, y=0, width=1000, height=800)
    right = ScreenRect(x=1000, y=0, width=1200, height=800)
    anchor = ScreenRect(x=1100, y=40, width=400, height=60)
    assert display_for_anchor(anchor, (left, right), left) == right


def test_empty_ocr_clears_live_translation() -> None:
    content = format_live_overlay(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.FAILURE,
            source_text=None,
            translated_text=None,
            error="empty_ocr_text",
        )
    )
    assert content.translation == ""
    assert content.title.startswith("实时")


def test_live_translate_failure_shows_error_not_old_text() -> None:
    content = format_live_overlay(
        TranslateJob(
            kind=JobKind.OCR,
            status=JobStatus.PARTIAL,
            source_text="Hello",
            translated_text=None,
            error="timeout",
        )
    )
    assert content.source == "Hello"
    assert content.translation == "timeout"


def test_rect_from_drag_canonicalizes() -> None:
    rect = rect_from_drag(80, 40, 20, 10)
    assert rect == ScreenRect(x=20, y=10, width=60, height=30)


def test_region_picker_start_returns_before_selection_and_can_cancel(
    monkeypatch,
) -> None:
    sessions = []

    class _FakeSession:
        def __init__(self, *, on_complete=None) -> None:
            self.on_complete = on_complete
            self.begun = False
            sessions.append(self)

        def begin(self) -> None:
            self.begun = True

        def complete(self, rect: ScreenRect | None) -> None:
            if self.on_complete is not None:
                self.on_complete(rect)

    monkeypatch.setattr(region_picker_module, "_PickerSession", _FakeSession)
    completed = []
    picker = region_picker_module.RegionPicker()

    picker.start(completed.append)

    assert sessions[0].begun is True
    assert completed == []
    picker.cancel()
    assert completed == [None]


def test_region_picker_preserves_one_frame_per_screen(monkeypatch) -> None:
    frames = ("primary", "secondary")
    screens = tuple(SimpleNamespace(frame=lambda frame=frame: frame) for frame in frames)
    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(
            NSMakeRect=lambda *values: values,
            NSScreen=SimpleNamespace(screens=lambda: screens),
        ),
    )

    assert region_picker_module._screen_frames() == frames


def test_region_picker_session_covers_and_closes_every_screen(monkeypatch) -> None:
    frames = ("primary", "secondary")
    created = []

    class _FakeWindow:
        def __init__(self) -> None:
            self.front_count = 0
            self.key_count = 0
            self.first_responder = None
            self.out_count = 0

        def orderFrontRegardless(self) -> None:
            self.front_count += 1

        def makeKeyAndOrderFront_(self, _sender) -> None:
            self.key_count += 1

        def makeFirstResponder_(self, view) -> None:
            self.first_responder = view

        def orderOut_(self, _sender) -> None:
            self.out_count += 1

    class _FakeView:
        def __init__(self, session) -> None:
            self.session = session

    class _FakeApplication:
        def __init__(self) -> None:
            self.activated = False

        def activateIgnoringOtherApps_(self, value) -> None:
            self.activated = bool(value)

    app = _FakeApplication()

    def make_panel(frame, session):
        window = _FakeWindow()
        view = _FakeView(session)
        created.append((frame, window, view))
        return window, view

    monkeypatch.setattr(region_picker_module, "_screen_frames", lambda: frames)
    monkeypatch.setattr(region_picker_module, "_make_picker_panel", make_panel)
    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(
            NSApplication=SimpleNamespace(sharedApplication=lambda: app),
        ),
    )
    session = region_picker_module._PickerSession()

    session.begin()

    assert [frame for frame, _window, _view in created] == list(frames)
    assert app.activated is True
    assert [window.front_count for _frame, window, _view in created] == [1, 1]
    assert [window.key_count for _frame, window, _view in created] == [1, 0]
    assert created[0][1].first_responder is created[0][2]

    session.complete(None)

    assert [window.out_count for _frame, window, _view in created] == [1, 1]
    assert [view.session for _frame, _window, view in created] == [None, None]
