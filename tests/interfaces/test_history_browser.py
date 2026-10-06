from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.features.history import TranslationHistory
from ai_translate.infrastructure.history import JsonHistoryStore
from ai_translate.interfaces.history import HistoryBrowser, WindowsHistoryPresenter
from ai_translate.interfaces.windows_qt import WindowsUiRuntime


def _job(text):
    return TranslateJob(JobKind.SELECTION, JobStatus.SUCCESS, text, f"译文 {text}")


def test_browser_keeps_selected_entry_when_new_results_arrive(tmp_path):
    history = TranslationHistory(JsonHistoryStore(tmp_path / "history.json"))
    reused = []
    browser = HistoryBrowser(history, reused.append)
    browser.set_enabled(True)
    history.record(_job("first"), "en", "zh")
    history.record(_job("second"), "en", "ja")
    browser.refresh()
    browser.select(1)
    selected = browser.selected
    history.record(_job("new"), "en", "ko")
    browser.reuse()
    browser.refresh()
    assert browser.index == 2
    assert browser.selected == selected
    assert reused == [selected]
    assert len(history.state.entries) == 3
    browser.select(99)
    browser.reuse()
    assert browser.selected is None
    assert reused == [selected]


def test_windows_history_signals_toggle_preview_reuse_and_clear(tmp_path):
    history = TranslationHistory(JsonHistoryStore(tmp_path / "history.json"))
    properties = {}
    signals = {}
    created = []
    presented = []
    reused = []
    window = SimpleNamespace(setProperty=lambda key, value: properties.update({key: value}))

    def create(name):
        created.append(name)
        return window

    runtime = create_autospec(WindowsUiRuntime, instance=True)
    runtime.call_soon.side_effect = lambda action: action()
    runtime.create_window.side_effect = create
    runtime.connect_signal.side_effect = lambda _window, signal, callback: signals.update({signal: callback})
    runtime.present_window.side_effect = lambda _window: presented.append(_window)
    presenter = WindowsHistoryPresenter(runtime, history, reused.append)
    presenter.show()
    assert properties["savingEnabled"] is False
    assert properties["canReuse"] is False
    assert "0/50" in properties["statusText"]
    signals["savingToggled(bool)"](True)
    history.record(_job("first"), "en", "zh")
    history.record(_job("second"), "en", "ja")
    presenter.show()
    assert created == ["History.qml"]
    assert properties["sourceText"] == "second"
    assert len(properties["entryLabels"]) == 2
    signals["entrySelected(int)"](1)
    assert properties["sourceText"] == "first"
    assert properties["translatedText"] == "译文 first"
    signals["reuseRequested()"]()
    assert reused == [history.state.entries[1]]
    signals["savingToggled(bool)"](False)
    assert len(history.state.entries) == 2
    assert properties["savingEnabled"] is False
    signals["clearRequested()"]()
    assert properties["sourceText"] == properties["translatedText"] == ""
    assert properties["canClear"] is False
    assert properties["canReuse"] is False
    assert TranslationHistory(JsonHistoryStore(tmp_path / "history.json")).state.entries == ()


def test_browser_shows_corruption_and_preserves_file_until_clear(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("broken", encoding="utf-8")
    browser = HistoryBrowser(TranslationHistory(JsonHistoryStore(path)), lambda _entry: None)
    browser.set_enabled(True)
    assert "无法读取" in browser.status
    assert path.read_text(encoding="utf-8") == "broken"
    browser.clear()
    browser.set_enabled(True)
    assert browser.history.state.enabled is True
    assert browser.history.error is None


def test_browser_reports_busy_reuse_without_changing_record(tmp_path):
    history = TranslationHistory(JsonHistoryStore(tmp_path / "history.json"))
    history.set_enabled(True)
    history.record(_job("saved"), "en", "zh")
    busy = [True]
    restored = []

    def restore(entry):
        if busy[0]:
            return False
        restored.append(entry)
        return True

    browser = HistoryBrowser(history, restore)
    browser.refresh()
    before = history.state
    browser.reuse()
    assert "正在翻译" in browser.status
    assert restored == []
    assert history.state == before
    busy[0] = False
    browser.reuse()
    assert restored == [before.entries[0]]
    assert "正在翻译" not in browser.status
    assert history.state == before


@pytest.mark.parametrize("platform", ["macOS", "Windows"])
def test_workspace_remains_busy_until_queued_result_is_applied(monkeypatch, platform):
    pending = []
    applied = []
    if platform == "macOS":
        import sys
        from ai_translate.interfaces.overlay import OverlayPresenter, _AppKitBackend

        monkeypatch.setitem(sys.modules, "Foundation", SimpleNamespace(
            NSThread=SimpleNamespace(isMainThread=lambda: False),
        ))
        monkeypatch.setitem(sys.modules, "PyObjCTools.AppHelper", SimpleNamespace(
            callAfter=pending.append,
        ))
        backend = _AppKitBackend.__new__(_AppKitBackend)
        backend._busy = False
        backend._pending_results = 0
        backend._show_on_main = applied.append
        presenter = OverlayPresenter.__new__(OverlayPresenter)
        presenter._impl = backend
    else:
        from ai_translate.interfaces.windows_qt import WindowsOverlayPresenter

        presenter = WindowsOverlayPresenter(SimpleNamespace(call_soon=pending.append))
        presenter._show = lambda content, **_kwargs: applied.append(content)

    assert presenter.translation_busy is False
    presenter.show(_job("queued"))
    assert presenter.translation_busy is True
    assert applied == []
    pending.pop(0)()
    assert presenter.translation_busy is False
    assert len(applied) == 1
