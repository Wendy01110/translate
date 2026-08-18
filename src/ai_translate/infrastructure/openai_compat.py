from __future__ import annotations

from typing import Any

import httpx


def chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def message_text(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    cleaned = content.strip()
    return cleaned or None


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
        response = client.post(
            chat_completions_url(base_url),
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
    except httpx.TimeoutException:
        return None, None, "timeout"
    except httpx.HTTPError:
        return None, None, "http_error"

    try:
        body = response.json()
    except ValueError:
        return response.status_code, None, "invalid_json"

    if not isinstance(body, dict):
        return response.status_code, None, "invalid_json"
    if response.status_code >= 400:
        return response.status_code, body, f"http_{response.status_code}"
    return response.status_code, body, None
