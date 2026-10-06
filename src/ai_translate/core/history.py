from dataclasses import dataclass

from ai_translate.core.models import JobKind

MAX_HISTORY_RECORDS = 50
MAX_HISTORY_TEXT_CHARS = 8000
MAX_HISTORY_BYTES = 1024 * 1024


@dataclass(frozen=True)
class HistoryEntry:
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    created_at: str
    kind: JobKind


@dataclass(frozen=True)
class HistoryState:
    enabled: bool = False
    entries: tuple[HistoryEntry, ...] = ()
