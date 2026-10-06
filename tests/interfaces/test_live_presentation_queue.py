import sys
from types import SimpleNamespace

import pytest

from ai_translate.core.models import ScreenRect
from ai_translate.features.ocr_translate import OcrTranslateService
from ai_translate.features.selection import SelectionTranslateService
from ai_translate.interfaces.live_overlay import LiveOverlayPresenter, _LiveOverlayBackend
from ai_translate.interfaces.listen import DesktopListener
from ai_translate.interfaces.windows_qt import WindowsLiveOverlayPresenter
from tests.support import FakeOcrEngine, FakeTranslator


class _Window:
    def __init__(self):
        self.visible = True
        self.front_calls = 0
        self.values = {}

    def setTitle_(self, value):
        self.values["title"] = value

    def orderFrontRegardless(self):
        self.visible = True
        self.front_calls += 1

    def orderOut_(self, _sender):
        self.visible = False

    def setProperty(self, name, value):
        self.values[name] = value


@pytest.fixture(params=["macOS", "Windows"])
def queued_live_ui(request, monkeypatch):
    pending = []
    main = [False]
    window = _Window()

    def dispatch(callback, *args):
        if main[0]:
            callback(*args)
        else:
            pending.append(lambda: callback(*args))

    if request.param == "macOS":
        monkeypatch.setitem(sys.modules, "Foundation", SimpleNamespace(
            NSThread=SimpleNamespace(isMainThread=lambda: main[0]),
        ))
        monkeypatch.setitem(sys.modules, "PyObjCTools.AppHelper", SimpleNamespace(callAfter=dispatch))
        monkeypatch.setattr("ai_translate.interfaces.live_overlay._prepare_overlay_window", lambda *_a, **_kw: None)
        monkeypatch.setattr("ai_translate.interfaces.live_overlay._set_scrollable_text", lambda view, text: view.update(text=text))
        backend = _LiveOverlayBackend.__new__(_LiveOverlayBackend)
        backend._window = window
        backend._source = {}
        backend._translation = {}
        backend._closing = False
        backend._placed = True
        backend._display_generation = 0
        backend.layout_window = lambda: None
        live = LiveOverlayPresenter()
        live._impl = backend
        render_text = lambda: backend._translation.get("text", "")
        during_layout = lambda callback: setattr(backend, "layout_window", callback)
    else:
        runtime = SimpleNamespace(
            call_soon=dispatch,
            present_window=lambda target: target.orderFrontRegardless(),
            hide_window=lambda target: setattr(target, "visible", False),
            set_no_activate=lambda _target: None,
        )
        live = WindowsLiveOverlayPresenter(runtime)
        live._window = window
        live._position = lambda: None
        render_text = lambda: window.values.get("translationText", "")
        during_layout = lambda callback: setattr(live, "_position", callback)

    translator = FakeTranslator()
    listener = DesktopListener(
        selection=SelectionTranslateService(translator),
        ocr_translate=OcrTranslateService(FakeOcrEngine(), translator),
        read_selected_text=lambda: "synthetic selection",
        capture_region=lambda: (b"synthetic frame", "image/png"),
        capture_rect=lambda _rect: (b"synthetic frame", "image/png"),
        presenter=live, live_presenter=live,
        selection_hotkey="alt+e", ocr_hotkey="alt+w", source_lang="en", target_lang="zh",
    )

    def activate():
        listener._live_generation += 1
        listener._live_rect = ScreenRect(100, 200, 280, 60)
        listener._live_running = True
        listener._live_stop.clear()
        live.set_anchor(listener._live_rect)

    def drain():
        main[0] = True
        while pending:
            pending.pop(0)()

    main[0] = True
    activate()
    main[0] = False
    return SimpleNamespace(
        live=live, listener=listener, window=window, pending=pending, main=main,
        activate=activate, drain=drain, render_text=render_text, during_layout=during_layout,
    )


def test_stopped_live_result_cannot_reopen_window(queued_live_ui):
    ui = queued_live_ui
    assert ui.listener.live_tick() == "show"
    assert ui.pending
    ui.main[0] = True
    ui.listener.stop_live()
    assert not ui.window.visible
    ui.drain()
    assert not ui.window.visible
    assert not ui.listener.live_running
    assert ui.render_text() == ""


def test_queued_result_is_discarded_after_language_change(queued_live_ui):
    ui = queued_live_ui
    assert ui.listener.live_tick() == "show"
    ui.listener.set_target_lang("en")
    ui.drain()
    assert ui.render_text() == ""


def test_queued_status_is_discarded_after_stop(queued_live_ui):
    ui = queued_live_ui
    ui.live.show_status("旧加载状态")
    ui.main[0] = True
    ui.listener.stop_live()
    ui.drain()
    assert not ui.window.visible
    assert ui.render_text() == ""


def test_background_stop_hides_the_existing_window(queued_live_ui):
    ui = queued_live_ui
    ui.listener.stop_live()
    assert ui.pending
    ui.drain()
    assert not ui.window.visible


def test_old_result_cannot_overwrite_restarted_session(queued_live_ui):
    ui = queued_live_ui
    assert ui.listener.live_tick() == "show"
    ui.main[0] = True
    ui.listener.stop_live()
    ui.activate()
    ui.live.show_status("新会话状态")
    ui.drain()
    assert ui.window.visible
    assert ui.render_text() != "你好"


def test_old_hide_cannot_hide_a_restarted_live_session(queued_live_ui):
    ui = queued_live_ui
    ui.listener.stop_live()
    assert ui.pending
    ui.main[0] = True
    ui.activate()
    ui.live.show_status("新会话状态")
    assert ui.window.visible
    ui.drain()
    assert ui.window.visible


@pytest.mark.parametrize("change", ["stop", "language"])
def test_state_change_during_ui_layout_does_not_front_window(queued_live_ui, change):
    ui = queued_live_ui
    assert ui.listener.live_tick() == "show"

    def change_once():
        ui.during_layout(lambda: None)
        if change == "stop":
            ui.listener.stop_live()
        else:
            ui.listener.set_target_lang("en")

    ui.during_layout(change_once)
    ui.drain()
    assert ui.window.front_calls == 0
    assert ui.window.visible is (change == "language")
    assert ui.listener.live_running is (change == "language")
