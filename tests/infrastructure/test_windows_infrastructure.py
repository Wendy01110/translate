import pytest

from ai_translate.core.errors import ImageSourceError
from ai_translate.core.models import ScreenRect
from ai_translate.infrastructure.windows_desktop import (
    WindowsClipboard,
    WindowsRectCapture,
    WindowsRegionScreenshot,
)


class _ClipboardApi:
    CF_UNICODETEXT = 13

    def __init__(self, value: str = "") -> None:
        self.value = value
        self.open_failures = 0
        self.opened = 0
        self.closed = 0

    def OpenClipboard(self) -> None:
        if self.open_failures > 0:
            self.open_failures -= 1
            raise RuntimeError("busy")
        self.opened += 1

    def CloseClipboard(self) -> None:
        self.closed += 1

    def IsClipboardFormatAvailable(self, format_id: int) -> bool:
        assert format_id == self.CF_UNICODETEXT
        return bool(self.value)

    def GetClipboardData(self, format_id: int) -> str:
        assert format_id == self.CF_UNICODETEXT
        return self.value

    def EmptyClipboard(self) -> None:
        self.value = ""

    def SetClipboardText(self, value: str, format_id: int) -> None:
        assert format_id == self.CF_UNICODETEXT
        self.value = value


def test_windows_clipboard_reads_and_writes_unicode_text() -> None:
    api = _ClipboardApi("Hello 世界")
    clipboard = WindowsClipboard(api_factory=lambda: api)
    assert clipboard.read() == "Hello 世界"
    clipboard.write("新的内容")
    assert api.value == "新的内容"
    assert api.opened == 2
    assert api.closed == 2


def test_windows_clipboard_retries_when_another_app_holds_it() -> None:
    api = _ClipboardApi("copied")
    api.open_failures = 2
    waits: list[float] = []
    clipboard = WindowsClipboard(api_factory=lambda: api, wait=waits.append)
    assert clipboard.read() == "copied"
    assert len(waits) == 2


def test_windows_rect_capture_returns_bounded_png() -> None:
    seen: list[ScreenRect] = []
    capture = WindowsRectCapture(
        grabber=lambda rect: seen.append(rect) or b"png-bytes"
    )
    assert capture.capture_rect(
        ScreenRect(x=30, y=40, width=-20, height=-24)
    ) == (b"png-bytes", "image/png")
    assert seen == [ScreenRect(x=10, y=16, width=20, height=24)]


def test_windows_rect_capture_rejects_tiny_region() -> None:
    capture = WindowsRectCapture(grabber=lambda _rect: b"must-not-run")
    with pytest.raises(ImageSourceError) as caught:
        capture.capture_rect(ScreenRect(x=0, y=0, width=10, height=10))
    assert caught.value.code == "region_too_small"


def test_windows_rect_capture_rejects_excessive_pixel_area() -> None:
    capture = WindowsRectCapture(grabber=lambda _rect: b"must-not-run")
    with pytest.raises(ImageSourceError) as caught:
        capture.capture_rect(ScreenRect(x=0, y=0, width=10000, height=10000))
    assert caught.value.code == "image_too_large"


def test_windows_region_screenshot_cancels_without_capture() -> None:
    calls: list[ScreenRect] = []
    capture = WindowsRegionScreenshot(
        pick_region=lambda: None,
        capture_rect=lambda rect: calls.append(rect) or (b"png", "image/png"),
    )
    with pytest.raises(ImageSourceError) as caught:
        capture.capture_region()
    assert caught.value.code == "screenshot_cancelled"
    assert calls == []


def test_windows_region_screenshot_captures_selected_rect() -> None:
    rect = ScreenRect(x=-100, y=20, width=200, height=80)
    capture = WindowsRegionScreenshot(
        pick_region=lambda: rect,
        capture_rect=lambda selected: (repr(selected).encode(), "image/png"),
    )
    data, mime_type = capture.capture_region()
    assert b"ScreenRect" in data
    assert mime_type == "image/png"
