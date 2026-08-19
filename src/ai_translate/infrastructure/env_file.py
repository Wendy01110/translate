from __future__ import annotations

from pathlib import Path

ALLOWED_ENV_KEYS = frozenset(
    {
        "OCR_ENGINE",
        "OCR_MIN_CONFIDENCE",
        "OCR_IMAGE_MODE",
        "TRANSLATE_SOURCE_LANG",
        "TRANSLATE_TARGET_LANG",
        "TRANSLATE_PROVIDER",
        "TRANSLATE_BASE_URL",
        "TRANSLATE_MODEL",
        "TRANSLATE_API_KEY",
        "TRANSLATE_REGION",
        "OCR_BASE_URL",
        "OCR_MODEL",
        "OCR_API_KEY",
        "HOTKEY_SELECTION",
        "HOTKEY_OCR",
    }
)
_FORBIDDEN_ENV_KEYS = frozenset(
    {
        "AUTHORIZATION",
    }
)


def upsert_env_values(path: Path, updates: dict[str, str]) -> None:
    cleaned = _validated_updates(updates)
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
    seen: set[str] = set()
    rewritten: list[str] = []
    for line in lines:
        key = _assignment_key(line)
        if key is not None and key in cleaned:
            rewritten.append(f"{key}={cleaned[key]}")
            seen.add(key)
        else:
            rewritten.append(line)
    for key, value in cleaned.items():
        if key not in seen:
            rewritten.append(f"{key}={value}")
    text = "\n".join(rewritten)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _validated_updates(updates: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in updates.items():
        if key in _FORBIDDEN_ENV_KEYS:
            raise ValueError("settings must not write secrets")
        if key not in ALLOWED_ENV_KEYS:
            raise ValueError(f"unsupported settings key: {key}")
        if not isinstance(value, str):
            raise ValueError(f"unsupported settings key: {key}")
        if "\n" in value or "\r" in value:
            raise ValueError("settings values must be a single line")
        cleaned[key] = value.strip()
    return cleaned


def _assignment_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, _, _rest = stripped.partition("=")
    return key.strip() or None
