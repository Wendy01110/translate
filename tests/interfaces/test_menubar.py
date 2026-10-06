import sys
from types import SimpleNamespace

import pytest

if sys.platform != "darwin":
    pytest.skip("macOS menu bar tests require fcntl", allow_module_level=True)

from ai_translate.interfaces import menubar
from ai_translate.interfaces.menubar import (
    consume_pending_input,
    consume_pending_settings,
    defer_menu_action,
    display_hotkey,
    menu_spec,
)


def test_settings_open_runs_once_after_menu_and_delayed_fire() -> None:
    holder = SimpleNamespace(pending_settings=False)
    holder.pending_settings = True
    assert consume_pending_settings(holder) is True
    assert holder.pending_settings is False
    assert consume_pending_settings(holder) is False


def test_input_open_runs_once() -> None:
    holder = SimpleNamespace(pending_input=True)
    assert consume_pending_input(holder) is True
    assert holder.pending_input is False
    assert consume_pending_input(holder) is False


def test_history_open_is_deferred_until_menu_closes_and_runs_once(monkeypatch):
    scheduled = []
    opened = []

    class NSObject:
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return self

        def performSelector_withObject_afterDelay_(self, selector, _object, delay):
            scheduled.append((selector, delay))

        @staticmethod
        def cancelPreviousPerformRequestsWithTarget_(_target):
            scheduled.clear()

    monkeypatch.setitem(sys.modules, "Foundation", SimpleNamespace(NSObject=NSObject))
    monkeypatch.setitem(sys.modules, "objc", SimpleNamespace(super=super))
    monkeypatch.setattr(menubar, "_MenuBarController", None)
    controller = menubar._menu_controller_class().alloc().initWithListener_permissionItem_liveItem_openSettings_openInput_(
        SimpleNamespace(present_error=lambda _message: None), None, None, None, None,
    )
    controller.open_history_cb = lambda: opened.append(True)
    controller.pending_history = False
    controller.openHistory_(None)
    assert opened == []
    assert scheduled == [("openHistoryNow:", 0.2)]
    controller.menuDidClose_(None)
    assert scheduled == [("openHistoryNow:", 0.05)]
    controller.openHistoryNow_(None)
    controller.openHistoryNow_(None)
    assert opened == [True]


def test_defer_menu_action_runs_after_scheduler() -> None:
    ran: list[int] = []
    delays: list[float] = []

    def scheduler(delay: float, callback) -> None:
        delays.append(delay)
        callback()

    defer_menu_action(lambda: ran.append(1), scheduler=scheduler)
    assert ran == [1]
    assert delays == [0.2]


def test_display_hotkey_uses_option_glyph() -> None:
    assert display_hotkey("alt+e") == "⌥E"
    assert display_hotkey("option+w") == "⌥W"
    assert display_hotkey("cmd+shift+t") == "⇧⌘T"


def test_menu_spec_lists_selection_ocr_live_input_and_quit() -> None:
    items = menu_spec("alt+e", "alt+w")
    assert items[0] == ("划词翻译  ⌥E", "selection")
    assert items[1] == ("截图翻译  ⌥W", "ocr")
    assert items[2] == ("实时翻译  ⌥Q", "live")
    assert items[3] == ("输入翻译…", "input")
    assert items[4] == ("历史记录…", "history")
    assert items[5] == ("辅助功能：已开启", "accessibility")
    assert items[-1] == ("退出", "quit")
    denied = menu_spec("alt+e", "alt+w", accessibility_ok=False)
    assert denied[5] == ("辅助功能：未开启，点此去设置", "accessibility")
    assert items[-2] == ("设置…", "settings")
    running = menu_spec("alt+e", "alt+w", live_running=True)
    assert running[2] == ("停止实时翻译  ⌥Q", "live")


def test_single_instance_lock_rejects_a_second_copy(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(menubar.Path, "home", staticmethod(lambda: tmp_path))
    menubar._LIVE.clear()
    assert menubar._acquire_single_instance() is True
    assert menubar._acquire_single_instance() is False
    for item in list(menubar._LIVE):
        close = getattr(item, "close", None)
        if callable(close):
            close()
    menubar._LIVE.clear()
