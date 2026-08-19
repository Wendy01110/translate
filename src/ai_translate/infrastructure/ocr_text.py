from __future__ import annotations

import re


_ELEMENT_PREFIX = re.compile(
    r"^(?:header|footer|title|text|table|page_number|figure|caption|"
    r"reference|equation)\s*\[\s*-?\d+(?:\.\d+)?"
    r"(?:\s*,\s*-?\d+(?:\.\d+)?){3}\s*\]\s*",
    flags=re.IGNORECASE,
)
_GROUNDING_DETECTION = re.compile(r"<\|det\|>.*?<\|/det\|>", flags=re.DOTALL)
_GROUNDING_REFERENCE_TAG = re.compile(r"<\|/?ref\|>")


def clean_ocr_text(value: str) -> str:
    without_grounding = _GROUNDING_REFERENCE_TAG.sub(
        "",
        _GROUNDING_DETECTION.sub("", value),
    )
    cleaned = "\n".join(
        _ELEMENT_PREFIX.sub("", line)
        for line in without_grounding.splitlines()
    )
    return cleaned.strip()
