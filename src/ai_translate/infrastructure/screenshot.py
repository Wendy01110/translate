from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from ai_translate.core.errors import ImageSourceError
from ai_translate.core.limits import MAX_CAPTURE_PIXELS, MAX_IMAGE_BYTES
from ai_translate.core.models import ScreenRect
from ai_translate.infrastructure.image_file import load_image_file


class RegionScreenshot:
    def __init__(
        self,
        *,
        runner: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
    ) -> None:
        self._runner = runner or subprocess.run

    def capture_region(self) -> tuple[bytes, str]:
        if sys.platform != "darwin":
            raise ImageSourceError("screenshot_unsupported")
        try:
            with tempfile.NamedTemporaryFile(prefix="ai-translate-", suffix=".png", delete=False) as handle:
                path = Path(handle.name)
            try:
                completed = self._runner(
                    ["screencapture", "-i", "-x", str(path)],
                    check=False,
                    capture_output=True,
                    timeout=180,
                )
                return _read_capture(path, completed.returncode)
            finally:
                path.unlink(missing_ok=True)
        except (OSError, subprocess.SubprocessError):
            raise ImageSourceError("screenshot_failed") from None


class RectCapture:
    def __init__(
        self,
        *,
        grabber: Callable[[ScreenRect], bytes] | None = None,
    ) -> None:
        self._grabber = grabber or _grab_rect_png

    def capture_rect(self, rect: ScreenRect) -> tuple[bytes, str]:
        if sys.platform != "darwin":
            raise ImageSourceError("screenshot_unsupported")
        canonical = rect.canonical()
        if not canonical.is_usable():
            raise ImageSourceError("region_too_small")
        if canonical.width * canonical.height > MAX_CAPTURE_PIXELS:
            raise ImageSourceError("image_too_large")
        data = self._grabber(canonical)
        if not data:
            raise ImageSourceError("screenshot_failed")
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageSourceError("image_too_large")
        return data, "image/png"


def appkit_to_quartz_rect(
    rect: ScreenRect,
    *,
    main_display_height: float,
) -> ScreenRect:
    canonical = rect.canonical()
    return ScreenRect(
        x=canonical.x,
        y=main_display_height - canonical.y - canonical.height,
        width=canonical.width,
        height=canonical.height,
    )


def _grab_rect_png(rect: ScreenRect) -> bytes:
    from AppKit import NSBitmapImageRep, NSPNGFileType
    from Quartz import (
        CGDisplayBounds,
        CGMainDisplayID,
        CGRectMake,
        CGWindowListCreateImage,
        kCGNullWindowID,
        kCGWindowImageDefault,
        kCGWindowListOptionOnScreenOnly,
    )

    main_bounds = CGDisplayBounds(CGMainDisplayID())
    capture_rect = appkit_to_quartz_rect(
        rect,
        main_display_height=float(main_bounds.size.height),
    )
    image = CGWindowListCreateImage(
        CGRectMake(
            capture_rect.x,
            capture_rect.y,
            capture_rect.width,
            capture_rect.height,
        ),
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )
    if image is None:
        return b""
    representation = NSBitmapImageRep.alloc().initWithCGImage_(image)
    if representation is None:
        return b""
    png = representation.representationUsingType_properties_(NSPNGFileType, None)
    if png is None:
        return b""
    return bytes(png)


def _read_capture(path: Path, returncode: int) -> tuple[bytes, str]:
    if returncode != 0:
        raise ImageSourceError("screenshot_cancelled")
    try:
        return load_image_file(path)
    except ImageSourceError as exc:
        if exc.code in {"image_not_found", "empty_image"}:
            raise ImageSourceError("screenshot_cancelled") from None
        if exc.code == "image_read_failed":
            raise ImageSourceError("screenshot_failed") from None
        raise


def command_preview() -> Sequence[str]:
    return ("screencapture", "-i", "-x")
