from pathlib import Path
import subprocess

import pytest

from ai_translate.core.errors import ImageSourceError
from ai_translate.core.models import ScreenRect
from ai_translate.infrastructure.screenshot import (
    RectCapture,
    RegionScreenshot,
    appkit_to_quartz_rect,
)


@pytest.fixture(autouse=True)
def _run_macos_screenshot_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai_translate.infrastructure.screenshot.sys.platform", "darwin")


def test_screenshot_reads_png_and_deletes_temp(tmp_path: Path) -> None:
    leftover = tmp_path / "marker"

    def runner(command, **_kwargs):
        path = Path(command[-1])
        path.write_bytes(b"png-bytes")
        leftover.write_text(str(path))
        return subprocess.CompletedProcess(command, 0, b"", b"")

    source = RegionScreenshot(runner=runner)
    image_bytes, mime_type = source.capture_region()
    assert image_bytes == b"png-bytes"
    assert mime_type == "image/png"
    assert not Path(leftover.read_text()).exists()


def test_screenshot_cancel_is_classified() -> None:
    def runner(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1, b"", b"")

    try:
        RegionScreenshot(runner=runner).capture_region()
        raise AssertionError("expected ImageSourceError")
    except ImageSourceError as exc:
        assert exc.code == "screenshot_cancelled"


def test_rect_capture_uses_canonical_region_and_png() -> None:
    seen: list[ScreenRect] = []

    def grabber(rect: ScreenRect) -> bytes:
        seen.append(rect)
        return b"png-bytes"

    image_bytes, mime_type = RectCapture(grabber=grabber).capture_rect(
        ScreenRect(x=80, y=40, width=-20, height=30)
    )
    assert image_bytes == b"png-bytes"
    assert mime_type == "image/png"
    assert seen == [ScreenRect(x=60, y=40, width=20, height=30)]


def test_rect_capture_rejects_tiny_region() -> None:
    try:
        RectCapture(grabber=lambda _rect: b"png").capture_rect(
            ScreenRect(x=0, y=0, width=4, height=4)
        )
        raise AssertionError("expected ImageSourceError")
    except ImageSourceError as exc:
        assert exc.code == "region_too_small"


def test_rect_capture_rejects_empty_grab() -> None:
    try:
        RectCapture(grabber=lambda _rect: b"").capture_rect(
            ScreenRect(x=0, y=0, width=80, height=40)
        )
        raise AssertionError("expected ImageSourceError")
    except ImageSourceError as exc:
        assert exc.code == "screenshot_failed"


def test_appkit_rect_is_flipped_into_quartz_display_coordinates() -> None:
    assert appkit_to_quartz_rect(
        ScreenRect(x=100, y=200, width=400, height=60),
        main_display_height=900,
    ) == ScreenRect(x=100, y=640, width=400, height=60)


def test_appkit_rect_conversion_supports_displays_above_main() -> None:
    assert appkit_to_quartz_rect(
        ScreenRect(x=-300, y=900, width=300, height=100),
        main_display_height=900,
    ) == ScreenRect(x=-300, y=-100, width=300, height=100)
