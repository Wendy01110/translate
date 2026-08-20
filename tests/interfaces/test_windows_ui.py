import pytest

from ai_translate.core.models import ScreenRect
from ai_translate.interfaces.windows_desktop import (
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


def test_windows_settings_do_not_offer_unavailable_vision_only_mode() -> None:
    values = {value for value, _label in windows_settings_engine_options()}
    assert values == {"auto", "paddle", "standard", "model"}


def test_windows_settings_offer_all_local_advanced_model_tiers() -> None:
    values = {value for value, _label in windows_settings_model_tier_options()}
    assert values == {"tiny", "small", "medium"}
