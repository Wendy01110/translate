from __future__ import annotations

import json
from typing import Any

import httpx

from ai_translate.infrastructure.http_response import (
    ResponseTooLarge,
    read_bounded_response,
)


def chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def completion_content(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, None
    first = choices[0]
    if not isinstance(first, dict):
        return None, None
    finish_reason = first.get("finish_reason")
    reason = finish_reason if isinstance(finish_reason, str) else None
    message = first.get("message")
    if not isinstance(message, dict):
        return None, reason
    content = message.get("content")
    if not isinstance(content, str):
        return None, reason
    cleaned = content.strip()
    return (cleaned or None), reason


def post_chat_completion(
    client: httpx.Client,
    *,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    payload: dict[str, Any],
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with client.stream(
            "POST",
            chat_completions_url(base_url),
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        ) as response:
            if response.status_code >= 400:
                return response.status_code, None, f"http_{response.status_code}"
            content = read_bounded_response(response)
    except ResponseTooLarge:
        return response.status_code, None, "response_too_large"
    except httpx.TimeoutException:
        return None, None, "timeout"
    except httpx.HTTPError:
        return None, None, "http_error"

    try:
        body = json.loads(content)
    except (ValueError, RecursionError):
        return response.status_code, None, "invalid_json"

    if not isinstance(body, dict):
        return response.status_code, None, "invalid_json"
    return response.status_code, body, None
