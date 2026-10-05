from __future__ import annotations

import json
import random
import re
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from ai_translate.config import TranslateSettings
from ai_translate.core.limits import MAX_TRANSLATION_CHARS
from ai_translate.core.models import JobStatus, TranslationRequest, TranslationResult
from ai_translate.infrastructure.http_response import (
    ResponseTooLarge,
    read_bounded_response,
)

_GOOGLE_URL = "https://translate.google.com/translate_a/single"
_BING_PAGE_URL = "https://www.bing.com/translator"
_BING_TRANSLATE_URL = "https://www.bing.com/ttranslatev3"
_DEEPL_WEB_URL = "https://www2.deepl.com/jsonrpc"
_GOOGLE_LANG = {"auto": "auto", "en": "en", "zh": "zh", "ja": "ja", "ko": "ko"}
_BING_LANG = {"en": "en", "zh": "zh-Hans", "ja": "ja", "ko": "ko"}
_DEEPL_LANG = {"auto": "auto", "en": "EN", "zh": "ZH", "ja": "JA", "ko": "KO"}
_BING_HELPER_RE = re.compile(r"params_AbusePreventionHelper\s*=\s*(\[[^\]]+\])")
_BING_IG_RE = re.compile(r'IG:"([A-F0-9]+)"')
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


class GoogleWebTranslator:
    def __init__(
        self,
        settings: TranslateSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
            follow_redirects=True,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        blocked = _precheck(request, "google_web")
        if blocked is not None:
            return blocked
        source = _GOOGLE_LANG.get(request.source_lang)
        target = _GOOGLE_LANG.get(request.target_lang)
        if source is None or target is None or target == "auto":
            return _failure(request, "google_web", "unsupported_language")
        params = {
            "client": "gtx",
            "dt": "t",
            "sl": source,
            "tl": target,
            "q": request.text,
        }
        try:
            url = httpx.URL(_GOOGLE_URL, params=params)
        except httpx.InvalidURL:
            return _failure(request, "google_web", "request_url_too_long")
        body, error = _send(
            self._client,
            "GET",
            url,
            timeout_seconds=self._settings.timeout_seconds,
        )
        if error:
            return _failure(request, "google_web", error)
        text = _google_text(body)
        if not text:
            return _failure(request, "google_web", "empty_translation")
        return _success(request, "google_web", text)


class BingWebTranslator:
    def __init__(
        self,
        settings: TranslateSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
            follow_redirects=True,
        )
        self._session: dict[str, str] | None = None

    def translate(self, request: TranslationRequest) -> TranslationResult:
        blocked = _precheck(request, "bing_web")
        if blocked is not None:
            return blocked
        target = _BING_LANG.get(request.target_lang)
        if target is None:
            return _failure(request, "bing_web", "unsupported_language")
        source = "auto-detect"
        if request.source_lang != "auto":
            mapped = _BING_LANG.get(request.source_lang)
            if mapped is None:
                return _failure(request, "bing_web", "unsupported_language")
            source = mapped
        session, session_error = self._session_values()
        if session_error or session is None:
            return _failure(request, "bing_web", session_error or "empty_response")
        query = urlencode({"isVertical": "1", "IG": session["ig"], "IID": "translator.5024"})
        body, error = _send(
            self._client,
            "POST",
            f"{_BING_TRANSLATE_URL}?{query}",
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": "https://www.bing.com",
                "Referer": "https://www.bing.com/translator",
            },
            data={
                "fromLang": source,
                "to": target,
                "text": request.text,
                "token": session["token"],
                "key": session["key"],
            },
            timeout_seconds=self._settings.timeout_seconds,
        )
        if error:
            return _failure(request, "bing_web", error)
        text = _bing_text(body)
        if not text:
            return _failure(request, "bing_web", "empty_translation")
        return _success(request, "bing_web", text)

    def _session_values(self) -> tuple[dict[str, str] | None, str | None]:
        if self._session is not None:
            return self._session, None
        body, error = _send(
            self._client,
            "GET",
            _BING_PAGE_URL,
            headers={"Accept": "text/html"},
            timeout_seconds=self._settings.timeout_seconds,
        )
        if error:
            return None, error
        html = body if isinstance(body, str) else ""
        parsed = parse_bing_page(html)
        if parsed is None:
            return None, "empty_response"
        self._session = parsed
        return parsed, None


class DeepLWebTranslator:
    def __init__(
        self,
        settings: TranslateSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            trust_env=False,
            follow_redirects=True,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        blocked = _precheck(request, "deepl_web")
        if blocked is not None:
            return blocked
        source = _DEEPL_LANG.get(request.source_lang)
        target = _DEEPL_LANG.get(request.target_lang)
        if source is None or target is None or target == "auto":
            return _failure(request, "deepl_web", "unsupported_language")
        payload = _deepl_rpc_body(request.text, source, target)
        body, error = _send(
            self._client,
            "POST",
            _DEEPL_WEB_URL,
            headers={"Content-Type": "application/json; charset=utf-8"},
            content=payload.encode("utf-8"),
            timeout_seconds=self._settings.timeout_seconds,
        )
        if error:
            return _failure(request, "deepl_web", error)
        result = body.get("result") if isinstance(body, dict) else None
        texts = result.get("texts") if isinstance(result, dict) else None
        if not isinstance(texts, list) or not texts:
            return _failure(request, "deepl_web", "empty_translation")
        text = texts[0].get("text") if isinstance(texts[0], dict) else None
        if not isinstance(text, str) or not text.strip():
            return _failure(request, "deepl_web", "empty_translation")
        return _success(request, "deepl_web", text.strip())


def _precheck(request: TranslationRequest, provider: str) -> TranslationResult | None:
    if len(request.text) > MAX_TRANSLATION_CHARS:
        return _failure(request, provider, "text_too_long")
    return None


def parse_bing_page(html: str) -> dict[str, str] | None:
    helper = _BING_HELPER_RE.search(html)
    ig = _BING_IG_RE.search(html)
    if helper is None or ig is None:
        return None
    try:
        values = json.loads(helper.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(values, list) or len(values) < 2:
        return None
    token = values[1]
    if not isinstance(token, str) or not token:
        return None
    return {"key": str(values[0]), "token": token, "ig": ig.group(1)}


def _bing_text(body: Any) -> str:
    if isinstance(body, dict) and body.get("statusCode"):
        return ""
    rows = body if isinstance(body, list) else None
    if not rows:
        return ""
    first = rows[0]
    translations = first.get("translations") if isinstance(first, dict) else None
    if not isinstance(translations, list) or not translations:
        return ""
    text = translations[0].get("text") if isinstance(translations[0], dict) else None
    if not isinstance(text, str):
        return ""
    return text.strip()


def _google_text(body: Any) -> str:
    if not isinstance(body, list) or not body:
        return ""
    chunks = body[0]
    if not isinstance(chunks, list):
        return ""
    parts: list[str] = []
    for item in chunks:
        if isinstance(item, list) and item and isinstance(item[0], str):
            parts.append(item[0])
    return "".join(parts).strip()


def _deepl_rpc_body(content: str, source: str, target: str) -> str:
    ident = 1000 * (random.randint(0, 99998) + 8300000) + 1
    timestamp = int(time.time() * 1000)
    i_counts = content.count("i")
    if i_counts:
        i_counts += 1
        timestamp = timestamp - (timestamp % i_counts) + i_counts
    data = json.dumps(
        {
            "id": ident,
            "jsonrpc": "2.0",
            "method": "LMT_handle_texts",
            "params": {
                "texts": [{"text": content, "requestAlternatives": 3}],
                "splitting": "newlines",
                "lang": {
                    "source_lang_user_selected": source,
                    "target_lang": target,
                },
                "timestamp": timestamp,
                "commonJobParams": {"wasSpoken": False, "transcribe_as": ""},
            },
        },
        separators=(",", ":"),
    )
    if (ident + 5) % 29 == 0 or (ident + 3) % 13 == 0:
        return data.replace('"method":"', '"method" : "')
    return data.replace('"method":"', '"method": "')


def _send(
    client: httpx.Client,
    method: str,
    url: str | httpx.URL,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: object | None = None,
    data: dict[str, str] | None = None,
    content: bytes | None = None,
    timeout_seconds: float,
) -> tuple[Any | None, str | None]:
    merged = dict(_BROWSER_HEADERS)
    if headers:
        merged.update(headers)
    try:
        with client.stream(
            method,
            url,
            headers=merged,
            params=params,
            json=json_body,
            data=data,
            content=content,
            timeout=timeout_seconds,
        ) as response:
            if response.status_code >= 400:
                return None, f"http_{response.status_code}"
            response_content = read_bounded_response(response)
    except ResponseTooLarge:
        return None, "response_too_large"
    except httpx.TimeoutException:
        return None, "timeout"
    except httpx.HTTPError:
        return None, "http_error"
    try:
        body = json.loads(response_content)
    except RecursionError:
        return None, "invalid_json"
    except ValueError:
        try:
            text = response_content.decode(response.encoding or "utf-8", errors="replace").strip()
        except LookupError:
            text = response_content.decode("utf-8", errors="replace").strip()
        return (text or None), (None if text else "invalid_json")
    return body, None


def _failure(
    request: TranslationRequest,
    provider: str,
    error: str,
) -> TranslationResult:
    return TranslationResult(
        status=JobStatus.FAILURE,
        source_text=request.text,
        translated_text=None,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
        model=provider,
        error=error,
    )


def _success(
    request: TranslationRequest,
    provider: str,
    text: str,
) -> TranslationResult:
    return TranslationResult(
        status=JobStatus.SUCCESS,
        source_text=request.text,
        translated_text=text,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
        model=provider,
    )
