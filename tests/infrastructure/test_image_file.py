from pathlib import Path

import pytest

from ai_translate.core.errors import ImageSourceError
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
