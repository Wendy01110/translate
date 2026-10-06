from datetime import datetime, timezone
from threading import Lock

from ai_translate.core.history import (
    MAX_HISTORY_RECORDS,
    MAX_HISTORY_TEXT_CHARS,
    HistoryEntry,
    HistoryState,
)
from ai_translate.core.models import JobStatus, TranslateJob
from ai_translate.core.ports import HistoryStorage


class TranslationHistory:
    def __init__(self, storage: HistoryStorage) -> None:
        self._storage = storage
        self._lock = Lock()
        self._load_failed = False
        self.error: str | None = None
        try:
            self._state = storage.load()
        except (OSError, ValueError):
            self._state = HistoryState()
            self._load_failed = True
            self.error = "历史文件无法读取，请清空后重新开启；翻译功能仍可使用。"

    @property
    def state(self) -> HistoryState:
        with self._lock:
            return self._state

    def set_enabled(self, enabled: bool) -> bool:
        with self._lock:
            if self._load_failed:
                return False
            return self._save(HistoryState(enabled, self._state.entries))

    def clear(self) -> bool:
        with self._lock:
            if not self._save(HistoryState(self._state.enabled)):
                return False
            self._load_failed = False
            return True

    def record(self, job: TranslateJob, source_lang: str, target_lang: str) -> bool:
        if job.status is not JobStatus.SUCCESS or not job.source_text or not job.translated_text:
            return False
        if (
            len(job.source_text) > MAX_HISTORY_TEXT_CHARS
            or len(job.translated_text) > MAX_HISTORY_TEXT_CHARS
            or not 0 < len(source_lang) <= 32
            or not 0 < len(target_lang) <= 32
        ):
            return False
        with self._lock:
            if not self._state.enabled or self._load_failed:
                return False
            entries = self._state.entries
            if entries and (
                entries[0].source_text == job.source_text
                and entries[0].translated_text == job.translated_text
                and entries[0].source_lang == source_lang
                and entries[0].target_lang == target_lang
                and entries[0].kind is job.kind
            ):
                return False
            entry = HistoryEntry(
                job.source_text, job.translated_text, source_lang, target_lang,
                datetime.now(timezone.utc).isoformat(), job.kind,
            )
            return self._save(HistoryState(True, (entry, *entries[:MAX_HISTORY_RECORDS - 1])))

    def _save(self, state: HistoryState) -> bool:
        try:
            self._state = self._storage.save(state)
        except (OSError, ValueError):
            self.error = "历史保存失败，已有记录未改变；翻译功能仍可使用。"
            return False
        self.error = None
        return True
