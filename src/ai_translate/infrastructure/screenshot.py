from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from ai_translate.core.errors import ImageSourceError
from ai_translate.infrastructure.image_file import MAX_IMAGE_BYTES


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


def _read_capture(path: Path, returncode: int) -> tuple[bytes, str]:
    if returncode != 0 or not path.is_file() or path.stat().st_size == 0:
        raise ImageSourceError("screenshot_cancelled")
    data = path.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageSourceError("image_too_large")
    return data, "image/png"


def command_preview() -> Sequence[str]:
    return ("screencapture", "-i", "-x")
