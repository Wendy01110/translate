import pytest

from ai_translate.core.models import ScreenRect
from ai_translate.interfaces.overlay import OverlayContent
from ai_translate.interfaces.windows_desktop import (
    WindowsOverlayPresenter,
    _set_windows_overlay_pinned,
    windows_hotkey_codes,
    windows_hotkey_label,
    windows_live_overlay_rect,
    windows_virtual_screen_rect,
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


def test_windows_overlay_is_only_topmost_when_pinned() -> None:
    class _Window:
        def __init__(self) -> None:
            self.topmost = None

        def attributes(self, name: str, value: object) -> None:
            assert name == "-topmost"
            self.topmost = value

    window = _Window()

    _set_windows_overlay_pinned(window, pinned=False)
    assert window.topmost is False

    _set_windows_overlay_pinned(window, pinned=True)
    assert window.topmost is True


def test_windows_overlay_raises_then_restores_or_keeps_pin_state() -> None:
    class _Root:
        def __init__(self) -> None:
            self.idle_callbacks = []

        def after_idle(self, callback) -> None:
            self.idle_callbacks.append(callback)

    class _Runtime:
        def __init__(self) -> None:
            self.root = _Root()

    class _Window:
        def __init__(self) -> None:
            self.topmost_events = []
            self.front_count = 0
            self.visible = False
            self.window_title = ""

        def title(self, value: str) -> None:
            self.window_title = value

        def deiconify(self) -> None:
            self.visible = True

        def attributes(self, name: str, value: object) -> None:
            assert name == "-topmost"
            self.topmost_events.append(value)

        def lift(self) -> None:
            self.front_count += 1

    class _Label:
        def __init__(self) -> None:
            self.text = ""

        def configure(self, *, text: str) -> None:
            self.text = text

    class _Text:
        def __init__(self) -> None:
            self.value = ""
            self.state = "disabled"

        def configure(self, *, state: str) -> None:
            self.state = state

        def delete(self, _start: str, _end: str) -> None:
            self.value = ""

        def insert(self, _start: str, value: str) -> None:
            self.value = value

    runtime = _Runtime()
    presenter = WindowsOverlayPresenter(runtime)
    window = _Window()
    pin_button = _Label()
    presenter._window = window
    presenter._title = _Label()
    presenter._source = _Text()
    presenter._translation = _Text()
    presenter._footnote = _Label()
    presenter._pin_button = pin_button
    content = OverlayContent(
        title="划词",
        source="Hello",
        translation="你好",
        footnote="Google 内置",
    )

    presenter._show(content)

    assert window.topmost_events == [True]
    assert window.front_count == 1
    assert len(runtime.root.idle_callbacks) == 1
    runtime.root.idle_callbacks.pop()()
    assert window.topmost_events == [True, False]
    assert pin_button.text == "置顶"

    presenter._toggle_pin()
    assert presenter._pinned is True
    assert window.topmost_events[-1] is True
    assert pin_button.text == "取消置顶"

    window.topmost_events.clear()
    runtime.root.idle_callbacks.clear()
    presenter._show(content)
    assert window.topmost_events == [True]
    assert runtime.root.idle_callbacks == []


def test_windows_settings_do_not_offer_unavailable_vision_only_mode() -> None:
    values = {value for value, _label in windows_settings_engine_options()}
    assert values == {"auto", "paddle", "standard", "model"}


def test_windows_settings_offer_all_local_advanced_model_tiers() -> None:
    values = {value for value, _label in windows_settings_model_tier_options()}
    assert values == {"tiny", "small", "medium"}
