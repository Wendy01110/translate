import sys
from types import SimpleNamespace

import pytest

from ai_translate.core.models import ScreenRect
from ai_translate.interfaces import windows_qt as windows_qt_module
from ai_translate.interfaces.overlay import OverlayContent
from ai_translate.interfaces.windows_desktop import (
    windows_active_screen_index,
    windows_hotkey_codes,
    windows_hotkey_label,
    windows_live_overlay_height,
    windows_live_overlay_rect,
    windows_monitor_rects,
    windows_region_hint_origin,
    windows_region_size_label,
    windows_virtual_screen_rect,
)
from ai_translate.interfaces.windows_qt import (
    WindowsOverlayPresenter,
    WindowsRegionPicker,
    WindowsTray,
)
from ai_translate.interfaces.windows_views import (
    windows_settings_engine_options,
    windows_settings_model_tier_options,
)


def test_windows_hotkey_codes_support_letters_digits_and_function_keys() -> None:
    assert windows_hotkey_codes("ctrl+alt+e") == (0x4003, ord("E"))
    assert windows_hotkey_codes("shift+7") == (0x4004, ord("7"))
    assert windows_hotkey_codes("alt+f5") == (0x4001, 0x74)


def test_windows_hotkey_codes_reject_unsupported_key() -> None:
    with pytest.raises(ValueError, match="Windows 不支持"):
        windows_hotkey_codes("alt+pageup")


def test_windows_hotkey_label_uses_windows_names() -> None:
    assert windows_hotkey_label("cmd+ctrl+q") == "Ctrl+Win+Q"


def test_windows_virtual_screen_supports_negative_coordinates() -> None:
    values = {76: -1920, 77: -200, 78: 4480, 79: 1640}
    assert windows_virtual_screen_rect(values.__getitem__) == ScreenRect(
        x=-1920,
        y=-200,
        width=4480,
        height=1640,
    )


def test_windows_monitor_rects_keep_each_negative_coordinate_display() -> None:
    screens = windows_monitor_rects(
        lambda: (
            ScreenRect(x=-1080, y=-258, width=1080, height=1920),
            ScreenRect(x=0, y=0, width=2560, height=1440),
        )
    )

    assert screens == (
        ScreenRect(x=-1080, y=-258, width=1080, height=1920),
        ScreenRect(x=0, y=0, width=2560, height=1440),
    )
    assert windows_active_screen_index(
        screens,
        ScreenRect(x=0, y=0, width=2560, height=1392),
    ) == 1


def test_windows_live_overlay_prefers_below_region() -> None:
    rect = windows_live_overlay_rect(
        ScreenRect(x=100, y=100, width=360, height=100),
        screen=ScreenRect(x=0, y=0, width=1920, height=1080),
    )
    assert rect.y > 200
    assert rect.width == 360


def test_windows_live_overlay_moves_above_region_at_bottom() -> None:
    anchor = ScreenRect(x=1700, y=980, width=300, height=80)
    rect = windows_live_overlay_rect(
        anchor,
        screen=ScreenRect(x=0, y=0, width=1920, height=1080),
    )
    assert rect.y + rect.height < anchor.y
    assert rect.x + rect.width <= 1920


def test_windows_live_overlay_height_grows_for_wrapped_content_with_a_bound() -> None:
    assert windows_live_overlay_height(80, screen_height=1080) == 112
    assert windows_live_overlay_height(168, screen_height=1080) == 168
    assert windows_live_overlay_height(400, screen_height=1080) == 240
    assert windows_live_overlay_height(400, screen_height=180) == 180
    assert windows_live_overlay_height(312, screen_height=1440, scale=2.0) == 312
    assert windows_live_overlay_height(600, screen_height=1440, scale=2.0) == 480


def test_windows_region_size_feedback_is_direction_independent() -> None:
    assert windows_region_size_label(100, 80, 460, 220) == "360 × 140 px"
    assert windows_region_size_label(460, 220, 100, 80) == "360 × 140 px"


def test_windows_region_hint_uses_pointer_display_inside_negative_virtual_screen() -> None:
    virtual = ScreenRect(x=-1080, y=-258, width=3640, height=1920)

    assert windows_region_hint_origin(
        virtual,
        ScreenRect(x=0, y=0, width=2560, height=1392),
    ) == (1098, 276)
    assert windows_region_hint_origin(
        virtual,
        ScreenRect(x=-1080, y=-258, width=1080, height=1920),
    ) == (18, 18)


def test_windows_overlay_raises_then_restores_or_keeps_pin_state() -> None:
    class _Runtime:
        def __init__(self) -> None:
            self.later = []
            self.topmost = []
            self.presented = []

        def center_window(self, _window) -> None:
            raise AssertionError("existing window should not be re-centered")

        def present_window(self, window, *, focus_source=False) -> None:
            self.presented.append((window, focus_source))

        def set_topmost(self, _window, *, topmost: bool) -> None:
            self.topmost.append(topmost)

        def call_later(self, delay: int, callback) -> None:
            self.later.append((delay, callback))

    class _Window:
        def __init__(self) -> None:
            self.values = {}

        def setProperty(self, name: str, value: object) -> None:
            self.values[name] = value

        def property(self, name: str) -> object:
            return self.values.get(name, "")

    runtime = _Runtime()
    presenter = WindowsOverlayPresenter(runtime)
    window = _Window()
    presenter._window = window
    content = OverlayContent(
        title="翻译",
        source="Hello",
        translation="你好",
        footnote="Google 内置",
        source_editable=True,
    )

    presenter._show(content)

    assert runtime.topmost == [True]
    assert runtime.presented == [(window, False)]
    assert len(runtime.later) == 1
    delay, restore = runtime.later.pop()
    assert delay == 35
    restore()
    assert runtime.topmost == [True, False]
    assert window.values["pinned"] is False

    presenter._toggle_pin()
    assert presenter._pinned is True
    assert runtime.topmost[-1] is True
    assert window.values["pinned"] is True

    runtime.topmost.clear()
    runtime.later.clear()
    presenter._show(content)
    assert runtime.topmost == [True]
    assert runtime.later == []


def test_windows_workspace_language_change_updates_session_without_translating() -> None:
    changed = []
    translated = []

    class _Runtime:
        def call_soon(self, callback) -> None:
            callback()

    presenter = WindowsOverlayPresenter(_Runtime())
    presenter._translate = translated.append
    presenter._target_language_options = (("zh", "中文"), ("ja", "日语"))
    presenter._target_language = "zh"
    presenter._target_language_changed = changed.append

    presenter._target_language_selected(1)
    presenter._target_language_selected(1)

    assert changed == ["ja"]
    assert translated == []


def test_windows_workspace_translate_action_has_single_busy_request(monkeypatch) -> None:
    threads = []

    class _Runtime:
        def call_soon(self, callback) -> None:
            callback()

    class _Window:
        def __init__(self) -> None:
            self.values = {
                "sourceText": "edited source",
                "translationText": "old result",
            }

        def setProperty(self, name: str, value: object) -> None:
            self.values[name] = value

        def property(self, name: str) -> object:
            return self.values.get(name, "")

    class _Thread:
        def __init__(self, *, target, daemon) -> None:
            threads.append((target, daemon))

        def start(self) -> None:
            return None

    presenter = WindowsOverlayPresenter(_Runtime())
    presenter._translate = lambda text: text
    presenter._source_editable = True
    presenter._window = _Window()
    monkeypatch.setattr(windows_qt_module.threading, "Thread", _Thread)

    presenter._request_translate("edited source")
    presenter._request_translate("edited source")

    assert presenter._busy is True
    assert len(threads) == 1
    assert presenter._window.values["translationText"] == ""
    assert presenter._window.values["busy"] is True
    assert presenter._window.values["sourceEditable"] is True


def test_windows_tray_menu_wires_workspace_settings_and_quit(monkeypatch) -> None:
    created_icons = []
    calls = []

    class _Signal:
        def __init__(self) -> None:
            self.callbacks = []

        def connect(self, callback) -> None:
            self.callbacks.append(callback)

        def emit(self, *args) -> None:
            for callback in tuple(self.callbacks):
                callback(*args)

    class _Menu:
        def __init__(self) -> None:
            self.items = []
            self.aboutToShow = _Signal()

        def addAction(self, action) -> None:
            self.items.append(action)

        def addSeparator(self) -> None:
            self.items.append(None)

        def deleteLater(self) -> None:
            return None

    class _Action:
        def __init__(self, *args) -> None:
            self.text = args[0] if len(args) == 2 else ""
            self.triggered = _Signal()

        def setText(self, text: str) -> None:
            self.text = text

    class _IconImage:
        def __init__(self, path: str) -> None:
            self.path = path

    class _Icon:
        class ActivationReason:
            Trigger = 1

        def __init__(self, image, parent) -> None:
            self.image = image
            self.parent = parent
            self.activated = _Signal()
            self.started = False
            self.stopped = False
            created_icons.append(self)

        def setToolTip(self, text: str) -> None:
            self.title = text

        def setContextMenu(self, menu) -> None:
            self.menu = menu

        def show(self) -> None:
            self.started = True

        def hide(self) -> None:
            self.stopped = True

        def deleteLater(self) -> None:
            return None

    listener = SimpleNamespace(
        selection_hotkey="alt+e",
        ocr_hotkey="alt+w",
        live_hotkey="alt+q",
        live_running=False,
        handle_selection=lambda: None,
        handle_ocr=lambda: None,
        handle_live_ocr=lambda: None,
    )
    monkeypatch.setitem(
        sys.modules,
        "PySide6.QtGui",
        SimpleNamespace(QAction=_Action, QIcon=_IconImage),
    )
    monkeypatch.setitem(
        sys.modules,
        "PySide6.QtWidgets",
        SimpleNamespace(QMenu=_Menu, QSystemTrayIcon=_Icon),
    )
    runtime = SimpleNamespace(app=object())
    tray = WindowsTray(
        runtime=runtime,
        listener=listener,
        open_input=lambda: calls.append("workspace"),
        open_settings=lambda: calls.append("settings"),
        open_history=lambda: calls.append("history"),
        quit_app=lambda: calls.append("quit"),
    )

    tray.start()

    assert len(created_icons) == 1
    icon = created_icons[0]
    assert icon.started is True
    assert icon.title == "AI Translate"
    assert icon.menu.items[4].text == "打开翻译工作区…"
    assert icon.menu.items[5].text == "历史记录…"
    assert icon.menu.items[6].text == "设置…"
    assert icon.menu.items[7].text == "退出 AI Translate"
    icon.menu.items[4].triggered.emit()
    icon.menu.items[5].triggered.emit()
    icon.menu.items[6].triggered.emit()
    icon.menu.items[7].triggered.emit()
    assert calls == ["workspace", "history", "settings", "quit"]

    tray.stop()
    assert icon.stopped is True


def test_windows_settings_do_not_offer_unavailable_vision_only_mode() -> None:
    values = {value for value, _label in windows_settings_engine_options()}
    assert values == {"auto", "paddle", "standard", "model"}


def test_windows_settings_offer_all_local_advanced_model_tiers() -> None:
    values = {value for value, _label in windows_settings_model_tier_options()}
    assert values == {"tiny", "small", "medium"}


def test_windows_qt_surfaces_keep_required_interaction_copy() -> None:
    qml = windows_qt_module._QML_DIRECTORY

    workspace = (qml / "Workspace.qml").read_text(encoding="utf-8")
    settings = (qml / "Settings.qml").read_text(encoding="utf-8")
    live = (qml / "LiveOverlay.qml").read_text(encoding="utf-8")
    picker = (qml / "RegionOverlay.qml").read_text(encoding="utf-8")

    assert all(
        text in workspace
        for text in ("目标语言", "原文", "译文", "翻译", "置顶", "复制译文")
    )
    assert all(text in settings for text in ("翻译", "OCR", "语言与热键", "应用", "保存"))
    assert all(text in live for text in ("实时 OCR", "原文", "译文", "停止"))
    assert all(text in picker for text in ("拖动选择要识别的区域", "Esc 取消"))


def test_windows_active_composition_uses_qt_without_pystray() -> None:
    source = windows_qt_module.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()
    assert "QApplication" in text
    assert "QSystemTrayIcon" in text
    assert "setQuitOnLastWindowClosed(False)" in text
    assert "pystray" not in text
    assert "tkinter" not in text


def test_windows_picker_ignores_release_without_a_started_drag() -> None:
    calls = []
    picker = WindowsRegionPicker(SimpleNamespace(call_soon=lambda callback: callback()))
    picker._finish = lambda rect: calls.append(rect)

    picker._release(SimpleNamespace(), 10.0, 20.0)

    assert calls == []


def test_windows_picker_can_finish_while_first_surface_is_being_presented(
    monkeypatch,
) -> None:
    completed = []
    destroyed = []

    class _Window:
        def __init__(self) -> None:
            self.signals = {}
            self.values = {}

        def setProperty(self, name: str, value: object) -> None:
            self.values[name] = value

    class _Runtime:
        def __init__(self) -> None:
            self.windows = []
            self.dispatched = False

        def create_window(self, _name, _properties):
            window = _Window()
            self.windows.append(window)
            return window

        def connect_signal(self, window, signature, callback) -> None:
            window.signals[signature] = callback

        def set_native_rect(self, _window, _rect) -> None:
            return None

        def present_window(self, _window) -> None:
            return None

        def process_events(self) -> None:
            if self.dispatched:
                return
            self.dispatched = True
            window = self.windows[0]
            window.signals["pressedAt(double,double)"](10.0, 20.0)
            window.signals["releasedAt(double,double)"](110.0, 70.0)

        def device_pixel_ratio(self, _window) -> float:
            return 1.0

        def destroy_window(self, window) -> None:
            destroyed.append(window)

        def call_later(self, _delay, callback) -> None:
            callback()

    screens = (
        ScreenRect(x=0, y=0, width=800, height=600),
        ScreenRect(x=800, y=0, width=800, height=600),
    )
    monkeypatch.setattr(
        windows_qt_module,
        "windows_virtual_screen_rect",
        lambda: ScreenRect(x=0, y=0, width=1600, height=600),
    )
    monkeypatch.setattr(windows_qt_module, "windows_monitor_rects", lambda: screens)
    monkeypatch.setattr(
        windows_qt_module,
        "windows_pointer_screen_rect",
        lambda: screens[0],
    )

    runtime = _Runtime()
    picker = WindowsRegionPicker(runtime)
    picker._begin(completed.append)

    assert completed == [ScreenRect(x=10.0, y=20.0, width=100.0, height=50.0)]
    assert destroyed == [runtime.windows[0]]
    assert len(runtime.windows) == 1
    assert picker._surfaces == []
