from pathlib import Path

import pytest

from ai_translate.infrastructure.env_file import upsert_env_values


def test_upsert_updates_existing_key_and_keeps_comments(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# keep\nOCR_ENGINE=auto\nTRANSLATE_API_KEY=secret\n",
        encoding="utf-8",
    )
    upsert_env_values(
        path,
        {
            "OCR_ENGINE": "vision",
            "OCR_MIN_CONFIDENCE": "0.7",
            "TRANSLATE_MODEL": "gpt-4.1-mini",
            "TRANSLATE_BASE_URL": "https://translate.example/v1",
            "TRANSLATE_API_KEY": "translate-test-key",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "# keep" in text
    assert "OCR_ENGINE=vision" in text
    assert "OCR_MIN_CONFIDENCE=0.7" in text
    assert "TRANSLATE_MODEL=gpt-4.1-mini" in text
    assert "TRANSLATE_BASE_URL=https://translate.example/v1" in text
    assert "TRANSLATE_API_KEY=translate-test-key" in text


def test_upsert_rejects_authorization_header(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    with pytest.raises(ValueError, match="secrets"):
        upsert_env_values(path, {"AUTHORIZATION": "Bearer nope"})
