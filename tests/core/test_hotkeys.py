import pytest

from ai_translate.core.hotkeys import (
    HotkeyMatcher,
    display_hotkey,
    format_hotkey_spec,
    hotkey_button_title,
    interpret_hotkey_press,
    parse_hotkey,
    to_pynput_hotkey,
)


class _Key:
    def __init__(
        self,
        *,
        name: str | None = None,
        vk: int | None = None,
        char: str | None = None,
    ) -> None:
        self.name = name
        self.vk = vk
        self.char = char


def test_hotkey_aliases_are_normalized() -> None:
    assert to_pynput_hotkey("alt+t") == "<alt>+t"
    assert to_pynput_hotkey("option+shift+o") == "<alt>+<shift>+o"
    assert to_pynput_hotkey("cmd+shift+t") == "<cmd>+<shift>+t"


@pytest.mark.parametrize("spec", ["", "t", "alt+", "alt+shift"])
def test_invalid_hotkeys_are_rejected(spec: str) -> None:
    with pytest.raises(ValueError):
        to_pynput_hotkey(spec)
    with pytest.raises(ValueError):
        parse_hotkey(spec)


def test_parse_option_letters_uses_macos_key_codes() -> None:
    selection = parse_hotkey("option+e")
    assert selection.modifiers == frozenset({"alt"})
    assert selection.key == "e"
    assert selection.mac_vk == 0x0E
    ocr = parse_hotkey("alt+w")
    assert ocr.modifiers == frozenset({"alt"})
    assert ocr.mac_vk == 0x0D


def test_matcher_fires_option_letter_by_key_code_not_character() -> None:
    fired: list[str] = []
    matcher = HotkeyMatcher()
    matcher.bind(parse_hotkey("alt+e"), lambda: fired.append("e"))
    matcher.bind(parse_hotkey("alt+w"), lambda: fired.append("w"))
    matcher.press(_Key(name="alt"))
    matcher.press(_Key(vk=0x0E, char="´"))
    matcher.press(_Key(vk=0x0D, char="∑"))
    assert fired == ["e", "w"]


def test_format_and_display_hotkey() -> None:
    spec = parse_hotkey("option+shift+e")
    assert format_hotkey_spec(spec) == "alt+shift+e"
    assert display_hotkey("cmd+shift+t") == "⇧⌘T"
    assert hotkey_button_title("alt+e", recording=False) == "⌥E"
    assert hotkey_button_title("alt+e", recording=True) == "按下快捷键…"


def test_interpret_hotkey_press_records_option_e() -> None:
    result = interpret_hotkey_press(key_code=0x0E, modifier_flags=1 << 19)
    assert result.kind == "captured"
    assert result.spec == "alt+e"


def test_interpret_hotkey_press_escape_cancels() -> None:
    assert interpret_hotkey_press(key_code=0x35, modifier_flags=0).kind == "cancel"


def test_interpret_hotkey_press_requires_modifier() -> None:
    result = interpret_hotkey_press(key_code=0x0E, modifier_flags=0)
    assert result.kind == "invalid"
    assert result.error is not None


def test_interpret_hotkey_press_ignores_modifier_only_keys() -> None:
    assert interpret_hotkey_press(key_code=0x3A, modifier_flags=1 << 19).kind == "ignore"


def test_matcher_ignores_key_when_modifier_is_missing() -> None:
    fired: list[str] = []
    matcher = HotkeyMatcher()
    matcher.bind(parse_hotkey("alt+e"), lambda: fired.append("e"))
    matcher.press(_Key(vk=0x0E, char="e"))
    assert fired == []
