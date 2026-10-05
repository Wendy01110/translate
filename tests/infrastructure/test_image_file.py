import io
from pathlib import Path

import pytest

from ai_translate.core.errors import ImageSourceError
from ai_translate.infrastructure import image_file
from ai_translate.infrastructure.image_file import MAX_IMAGE_BYTES, load_image_file


def test_load_png_returns_bytes_and_mime(tmp_path: Path) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"png-bytes")
    image_bytes, mime_type = load_image_file(path)
    assert image_bytes == b"png-bytes"
    assert mime_type == "image/png"


def test_load_jpeg_uses_jpeg_mime(tmp_path: Path) -> None:
    path = tmp_path / "shot.jpg"
    path.write_bytes(b"jpeg-bytes")
    _image_bytes, mime_type = load_image_file(path)
    assert mime_type == "image/jpeg"


def test_missing_file_is_classified(tmp_path: Path) -> None:
    with pytest.raises(ImageSourceError) as captured:
        load_image_file(tmp_path / "missing.png")
    assert captured.value.code == "image_not_found"


def test_unsupported_type_is_classified(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"not-an-image")
    with pytest.raises(ImageSourceError) as captured:
        load_image_file(path)
    assert captured.value.code == "unsupported_image_type"


def test_oversize_file_is_classified(tmp_path: Path) -> None:
    path = tmp_path / "huge.png"
    path.write_bytes(b"x" * (MAX_IMAGE_BYTES + 1))
    with pytest.raises(ImageSourceError) as captured:
        load_image_file(path)
    assert captured.value.code == "image_too_large"


def test_file_at_exact_limit_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"x" * MAX_IMAGE_BYTES)
    data, mime_type = load_image_file(path)
    assert len(data) == MAX_IMAGE_BYTES
    assert mime_type == "image/png"


@pytest.mark.parametrize(
    ("contents", "error"),
    [(b"x" * 10, "image_too_large"), (b"", "empty_image")],
)
def test_actual_bytes_are_bounded_when_file_changes_after_stat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contents: bytes, error: str,
) -> None:
    path = tmp_path / "changing.png"
    path.write_bytes(b"x")
    monkeypatch.setattr(image_file, "MAX_IMAGE_BYTES", 8)
    reads: list[int] = []

    class ChangedFile(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            reads.append(size)
            return super().read(size)

    stream = ChangedFile(contents)
    original_open = Path.open
    monkeypatch.setattr(
        Path, "open",
        lambda self, *args, **kwargs: stream if self == path else original_open(self, *args, **kwargs),
    )
    with pytest.raises(ImageSourceError) as captured:
        load_image_file(path)
    assert captured.value.code == error
    assert reads == [9]
    assert stream.closed is True


@pytest.mark.parametrize("during_read", [False, True])
@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (FileNotFoundError, "image_not_found"),
        (PermissionError, "image_read_failed"),
        (OSError, "image_read_failed"),
    ],
)
def test_file_open_and_read_errors_are_classified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, during_read: bool,
    failure: type[OSError], error: str,
) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"synthetic")

    class FailedRead(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            raise failure("Synthetic OS detail")

    stream = FailedRead()
    original_open = Path.open

    def open_file(self, *args, **kwargs):
        if self != path:
            return original_open(self, *args, **kwargs)
        if during_read:
            return stream
        raise failure("Synthetic OS detail")

    monkeypatch.setattr(Path, "open", open_file)
    with pytest.raises(ImageSourceError) as captured:
        load_image_file(path)
    assert str(captured.value) == error
    if during_read:
        assert stream.closed is True


def test_file_stat_permission_error_is_classified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "page.png"
    path.write_bytes(b"synthetic")
    original_stat = Path.stat

    def stat_file(self, *args, **kwargs):
        if self == path:
            raise PermissionError("Synthetic OS detail")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat_file)
    with pytest.raises(ImageSourceError) as captured:
        load_image_file(path)
    assert str(captured.value) == "image_read_failed"
