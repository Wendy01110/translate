from __future__ import annotations

import httpx

MAX_RESPONSE_BYTES = 2_000_000


class ResponseTooLarge(Exception):
    pass


def read_bounded_response(
    response: httpx.Response,
    *,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> bytes:
    content = bytearray()
    for chunk in response.iter_bytes(chunk_size=64 * 1024):
        if len(content) + len(chunk) > max_bytes:
            raise ResponseTooLarge
        content.extend(chunk)
    return bytes(content)
