from __future__ import annotations

from pathlib import Path

from ai_translate.core.errors import ImageSourceError


MAX_IMAGE_BYTES = 20 * 1024 * 1024
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
    if not file_path.is_file():
        raise ImageSourceError("image_not_found")
    suffix = file_path.suffix.lower()
    mime_type = _MIME_BY_SUFFIX.get(suffix)
    if mime_type is None:
        raise ImageSourceError("unsupported_image_type")
    size = file_path.stat().st_size
    if size <= 0:
        raise ImageSourceError("empty_image")
    if size > MAX_IMAGE_BYTES:
        raise ImageSourceError("image_too_large")
    return file_path.read_bytes(), mime_type
