import ai_translate.interfaces.region_picker as region_picker_module
from ai_translate.core.models import JobKind, JobStatus, ScreenRect, TranslateJob
from ai_translate.interfaces.live_overlay import (
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
