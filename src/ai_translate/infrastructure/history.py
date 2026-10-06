import json
import os
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from ai_translate.core.history import (
    MAX_HISTORY_BYTES,
    MAX_HISTORY_RECORDS,
    MAX_HISTORY_TEXT_CHARS,
    HistoryEntry,
    HistoryState,
)
from ai_translate.core.models import JobKind


def default_history_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "AI Translate" / "history.json"


class JsonHistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> HistoryState:
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(MAX_HISTORY_BYTES + 1)
        except FileNotFoundError:
            return HistoryState()
        if len(raw) > MAX_HISTORY_BYTES:
            raise ValueError("history_too_large")
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):
            raise ValueError("invalid_history") from None
        if (
            not isinstance(data, dict)
            or type(data.get("version")) is not int
            or data.get("version") != 1
            or type(data.get("enabled")) is not bool
            or not isinstance(data.get("entries"), list)
            or len(data["entries"]) > MAX_HISTORY_RECORDS
        ):
            raise ValueError("invalid_history")
        entries = tuple(self._entry(item) for item in data["entries"])
        return HistoryState(data["enabled"], entries)

    @staticmethod
    def _entry(item: object) -> HistoryEntry:
        names = {"source_text", "translated_text", "source_lang", "target_lang", "created_at", "kind"}
        if not isinstance(item, dict) or set(item) != names:
            raise ValueError("invalid_history")
        for name in names:
            value = item[name]
            limit = MAX_HISTORY_TEXT_CHARS if name.endswith("text") else 64
            if not isinstance(value, str) or not value or len(value) > limit:
                raise ValueError("invalid_history")
        if len(item["source_lang"]) > 32 or len(item["target_lang"]) > 32:
            raise ValueError("invalid_history")
        try:
            datetime.fromisoformat(item["created_at"])
            kind = JobKind(item["kind"])
        except ValueError:
            raise ValueError("invalid_history") from None
        return HistoryEntry(**{**item, "kind": kind})

    def save(self, state: HistoryState) -> HistoryState:
        state = HistoryState(state.enabled, state.entries[:MAX_HISTORY_RECORDS])
        raw = self._encode(state)
        while len(raw) > MAX_HISTORY_BYTES and state.entries:
            state = HistoryState(state.enabled, state.entries[:-1])
            raw = self._encode(state)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix="history-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return state

    @staticmethod
    def _encode(state: HistoryState) -> bytes:
        return (json.dumps({
            "version": 1,
            "enabled": state.enabled,
            "entries": [asdict(entry) for entry in state.entries],
        }, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
