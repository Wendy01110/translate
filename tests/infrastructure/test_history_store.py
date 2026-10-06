import json
import os
from dataclasses import asdict

import pytest

from ai_translate.core.history import MAX_HISTORY_BYTES, HistoryEntry, HistoryState
from ai_translate.core.models import JobKind
from ai_translate.infrastructure.history import JsonHistoryStore, default_history_path


def entry(text="Hello"):
    return HistoryEntry(text, "译" * len(text), "en", "zh", "2026-10-06T00:00:00+00:00", JobKind.SELECTION)


def test_history_round_trip_and_new_file_is_private(tmp_path):
    path = tmp_path / "data" / "history.json"
    store = JsonHistoryStore(path)
    assert store.load() == HistoryState()
    assert not path.exists()
    state = HistoryState(True, (entry(),))
    assert store.save(state) == state
    assert store.load() == state
    if os.name == "posix":
        assert path.stat().st_mode & 0o077 == 0
    data = json.loads(path.read_text())
    assert set(data["entries"][0]) == set(asdict(entry()))


def test_history_unicode_file_budget_retains_newest_whole_records(tmp_path):
    store = JsonHistoryStore(tmp_path / "history.json")
    entries = tuple(entry(str(index) + "中" * 7998) for index in range(50))
    retained = store.save(HistoryState(True, entries))
    assert 0 < len(retained.entries) < len(entries)
    assert retained.entries == entries[:len(retained.entries)]
    assert store.path.stat().st_size <= MAX_HISTORY_BYTES
    assert store.load() == retained


@pytest.mark.parametrize("raw", [
    b"not json", b"[]", b'{"version":1,"enabled":"true","entries":[]}',
    b'{"version":true,"enabled":false,"entries":[]}',
    b'{"version":1,"enabled":true,"entries":[{}]}',
    b"[" * 4000 + b"]" * 4000,
])
def test_corrupt_history_is_rejected_without_changing_file(tmp_path, raw):
    path = tmp_path / "history.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="invalid_history"):
        JsonHistoryStore(path).load()
    assert path.read_bytes() == raw


def test_history_load_rejects_oversized_file(tmp_path):
    path = tmp_path / "history.json"
    path.write_bytes(b"x" * (MAX_HISTORY_BYTES + 1))
    with pytest.raises(ValueError, match="history_too_large"):
        JsonHistoryStore(path).load()


def test_history_replace_failure_keeps_previous_file_and_removes_temporary(tmp_path, monkeypatch):
    store = JsonHistoryStore(tmp_path / "history.json")
    store.save(HistoryState(True, (entry(),)))
    before = store.path.read_bytes()

    def fail(_source, _target):
        raise OSError("unavailable")

    monkeypatch.setattr("ai_translate.infrastructure.history.os.replace", fail)
    with pytest.raises(OSError):
        store.save(HistoryState(False))
    assert store.path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [store.path]


@pytest.mark.parametrize("platform, suffix", [
    ("darwin", "Library/Application Support/AI Translate/history.json"),
    ("win32", "AppData/Roaming/AI Translate/history.json"),
])
def test_history_path_is_outside_project_config(tmp_path, monkeypatch, platform, suffix):
    monkeypatch.setattr("ai_translate.infrastructure.history.sys.platform", platform)
    monkeypatch.setattr("ai_translate.infrastructure.history.Path.home", lambda: tmp_path)
    monkeypatch.delenv("APPDATA", raising=False)
    assert default_history_path() == tmp_path / suffix
