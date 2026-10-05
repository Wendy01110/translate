from collections.abc import Sequence

from ai_translate.core.limits import (
    MAX_IMAGE_BYTES,
    MAX_OCR_BATCH_BYTES,
    MAX_OCR_PAGES,
)


def ocr_pages_error(pages: Sequence[tuple[bytes, str]]) -> str | None:
    page_count = len(pages)
    if page_count == 0:
        return "empty_image"
    if page_count > MAX_OCR_PAGES:
        return "ocr_too_many_pages"
    total_bytes = 0
    for image_bytes, _mime_type in pages:
        image_size = len(image_bytes)
        if image_size == 0:
            return "empty_image"
        if image_size > MAX_IMAGE_BYTES:
            return "image_too_large"
        total_bytes += image_size
        if total_bytes > MAX_OCR_BATCH_BYTES:
            return "ocr_batch_too_large"
    return None
