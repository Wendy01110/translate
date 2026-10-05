from __future__ import annotations

from pathlib import Path

from ai_translate.core.errors import ImageSourceError
from ai_translate.core.limits import MAX_IMAGE_BYTES


_MIME_BY_SUFFIX = {
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def load_image_file(path: str | Path) -> tuple[bytes, str]:
    file_path = Path(path)
    try:
        if not file_path.is_file():
            raise ImageSourceError("image_not_found")
        mime_type = _MIME_BY_SUFFIX.get(file_path.suffix.lower())
        if mime_type is None:
            raise ImageSourceError("unsupported_image_type")
        size = file_path.stat().st_size
        if size <= 0:
            raise ImageSourceError("empty_image")
        if size > MAX_IMAGE_BYTES:
            raise ImageSourceError("image_too_large")
        with file_path.open("rb") as stream:
            data = stream.read(MAX_IMAGE_BYTES + 1)
    except (FileNotFoundError, IsADirectoryError):
        raise ImageSourceError("image_not_found") from None
    except OSError:
        raise ImageSourceError("image_read_failed") from None
    if not data:
        raise ImageSourceError("empty_image")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageSourceError("image_too_large")
    return data, mime_type
