from pathlib import Path
import subprocess

import pytest

from ai_translate.core.errors import ImageSourceError
from ai_translate.core.models import ScreenRect
from ai_translate.infrastructure import image_file
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


@pytest.mark.parametrize(
    "failure",
    [OSError("Synthetic OS detail"), subprocess.TimeoutExpired("synthetic", 180)],
)
def test_screenshot_command_failures_are_classified_and_cleaned(failure: Exception) -> None:
    paths: list[Path] = []

    def runner(command, **_kwargs):
        path = Path(command[-1])
        paths.append(path)
        path.write_bytes(b"synthetic")
        raise failure

    with pytest.raises(ImageSourceError) as captured:
        RegionScreenshot(runner=runner).capture_region()
    assert str(captured.value) == "screenshot_failed"
    assert len(paths) == 1
    assert not paths[0].exists()


@pytest.mark.parametrize("remove_file", [False, True])
def test_screenshot_empty_or_missing_file_is_cancelled(remove_file: bool) -> None:
    paths: list[Path] = []

    def runner(command, **_kwargs):
        path = Path(command[-1])
        paths.append(path)
        if remove_file:
            path.unlink()
        return subprocess.CompletedProcess(command, 0, b"", b"")

    with pytest.raises(ImageSourceError) as captured:
        RegionScreenshot(runner=runner).capture_region()
    assert captured.value.code == "screenshot_cancelled"
    assert not paths[0].exists()


def test_screenshot_temp_file_failure_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    def create_temp(**_kwargs):
        raise OSError("Synthetic OS detail")

    monkeypatch.setattr("ai_translate.infrastructure.screenshot.tempfile.NamedTemporaryFile", create_temp)
    with pytest.raises(ImageSourceError) as captured:
        RegionScreenshot(runner=lambda *_args, **_kwargs: None).capture_region()
    assert str(captured.value) == "screenshot_failed"


def test_screenshot_file_uses_image_read_limit_and_is_cleaned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image_file, "MAX_IMAGE_BYTES", 8)
    paths: list[Path] = []

    def runner(command, **_kwargs):
        path = Path(command[-1])
        paths.append(path)
        path.write_bytes(b"x" * 9)
        return subprocess.CompletedProcess(command, 0, b"", b"")

    with pytest.raises(ImageSourceError) as captured:
        RegionScreenshot(runner=runner).capture_region()
    assert captured.value.code == "image_too_large"
    assert not paths[0].exists()


def test_screenshot_file_permission_error_is_classified_and_cleaned(monkeypatch: pytest.MonkeyPatch) -> None:
    paths: list[Path] = []
    original_open = Path.open

    def open_file(self, mode="r", *args, **kwargs):
        if self in paths and mode == "rb":
            raise PermissionError("Synthetic OS detail")
        return original_open(self, mode, *args, **kwargs)

    def runner(command, **_kwargs):
        path = Path(command[-1])
        paths.append(path)
        path.write_bytes(b"synthetic")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(Path, "open", open_file)
    with pytest.raises(ImageSourceError) as captured:
        RegionScreenshot(runner=runner).capture_region()
    assert str(captured.value) == "screenshot_failed"
    assert not paths[0].exists()


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


def test_rect_capture_rejects_excessive_pixel_area_before_grabbing() -> None:
    calls: list[ScreenRect] = []
    capture = RectCapture(grabber=lambda rect: calls.append(rect) or b"png")
    with pytest.raises(ImageSourceError) as captured:
        capture.capture_rect(ScreenRect(x=0, y=0, width=10000, height=10000))
    assert captured.value.code == "image_too_large"
    assert calls == []


def test_rect_capture_accepts_exact_pixel_limit() -> None:
    rect = ScreenRect(x=-100, y=20, width=8000, height=5000)
    calls: list[ScreenRect] = []
    capture = RectCapture(grabber=lambda selected: calls.append(selected) or b"png")
    assert capture.capture_rect(rect) == (b"png", "image/png")
    assert calls == [rect]


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
