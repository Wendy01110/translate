from pathlib import Path
import subprocess

from ai_translate.core.errors import ImageSourceError
from ai_translate.infrastructure.screenshot import RegionScreenshot


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
