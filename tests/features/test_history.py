from dataclasses import replace

import pytest

from ai_translate.core.history import MAX_HISTORY_RECORDS, HistoryState
from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.features.history import TranslationHistory


class Store:
    def __init__(self, state=HistoryState(), load_error=False):
        self.state = state
        self.load_error = load_error
        self.fail_save = False
        self.writes = 0

    def load(self):
        if self.load_error:
            raise ValueError("invalid_history")
        return self.state

    def save(self, state):
        if self.fail_save:
            raise OSError("unavailable")
        self.writes += 1
        self.state = state
        return state


def job(text="Hello"):
    return TranslateJob(JobKind.SELECTION, JobStatus.SUCCESS, text, "你好")


def test_history_is_disabled_until_user_enables_it():
    store = Store()
    history = TranslationHistory(store)
    assert not history.record(job(), "en", "zh")
    assert store.writes == 0
    assert history.set_enabled(True)
    assert history.record(job(), "en", "zh")
    assert history.state.entries[0].source_text == "Hello"
    assert history.set_enabled(False)
    assert not history.record(job("Second"), "en", "zh")
    assert len(history.state.entries) == 1


@pytest.mark.parametrize("changes", [
    {"status": JobStatus.FAILURE}, {"status": JobStatus.PARTIAL},
    {"source_text": ""}, {"translated_text": None},
    {"source_text": "a" * 8001}, {"translated_text": "译" * 8001},
])
def test_history_rejects_failed_empty_or_oversized_results(changes):
    history = TranslationHistory(Store(HistoryState(True)))
    assert not history.record(replace(job(), **changes), "en", "zh")
    assert history.state.entries == ()


def test_history_deduplicates_consecutive_results_but_retains_language_changes():
    history = TranslationHistory(Store(HistoryState(True)))
    assert history.record(job(), "en", "zh")
    assert not history.record(job(), "en", "zh")
    assert history.record(job(), "en", "ja")
    assert [entry.target_lang for entry in history.state.entries] == ["ja", "zh"]


def test_history_retains_newest_records_and_clear_preserves_enabled_state():
    history = TranslationHistory(Store(HistoryState(True)))
    for number in range(60):
        assert history.record(job(str(number)), "en", "zh")
    assert len(history.state.entries) == MAX_HISTORY_RECORDS
    assert history.state.entries[0].source_text == "59"
    assert history.state.entries[-1].source_text == "10"
    assert history.clear()
    assert history.state == HistoryState(True)


def test_history_write_failure_preserves_existing_state():
    store = Store(HistoryState(True))
    history = TranslationHistory(store)
    assert history.record(job(), "en", "zh")
    before = history.state
    store.fail_save = True
    assert not history.record(job("Second"), "en", "zh")
    assert not history.clear()
    assert history.state == before
    assert history.error


def test_corrupt_history_is_not_overwritten_until_explicit_clear():
    store = Store(load_error=True)
    history = TranslationHistory(store)
    assert history.error
    assert not history.set_enabled(True)
    assert not history.record(job(), "en", "zh")
    assert store.writes == 0
    assert history.clear()
    assert history.error is None
    assert history.set_enabled(True)
