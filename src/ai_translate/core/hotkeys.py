from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

_MODIFIER_NAMES = {
    "alt": "alt",
    "option": "alt",
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "cmd": "cmd",
    "command": "cmd",
    "super": "cmd",
    "win": "cmd",
}

_PYNPUT_MODIFIERS = {
    "alt": "<alt>",
    "ctrl": "<ctrl>",
    "shift": "<shift>",
    "cmd": "<cmd>",
}

_MODIFIER_ORDER = ("ctrl", "alt", "shift", "cmd")
_DISPLAY_MARKS = (
    ("ctrl", "⌃"),
    ("alt", "⌥"),
    ("shift", "⇧"),
    ("cmd", "⌘"),
)
RECORDING_PROMPT = "按下快捷键…"
_MAC_FLAG_SHIFT = 1 << 17
_MAC_FLAG_CONTROL = 1 << 18
_MAC_FLAG_OPTION = 1 << 19
_MAC_FLAG_COMMAND = 1 << 20
_MAC_MODIFIER_KEY_CODES = frozenset(
    {0x36, 0x37, 0x38, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F}
)
_MAC_ESCAPE_KEY_CODE = 0x35

# macOS ANSI virtual key codes. Option+letter is matched by key code, not by
# the character Option would type (for example Option+E is ´, Option+W is ∑).
_MAC_ANSI_VK = {
    "a": 0x00,
    "s": 0x01,
    "d": 0x02,
    "f": 0x03,
    "h": 0x04,
    "g": 0x05,
    "z": 0x06,
    "x": 0x07,
    "c": 0x08,
    "v": 0x09,
    "b": 0x0B,
    "q": 0x0C,
    "w": 0x0D,
    "e": 0x0E,
    "r": 0x0F,
    "y": 0x10,
    "t": 0x11,
    "1": 0x12,
    "2": 0x13,
    "3": 0x14,
    "4": 0x15,
    "6": 0x16,
    "5": 0x17,
    "9": 0x19,
    "7": 0x1A,
    "8": 0x1C,
    "0": 0x1D,
    "o": 0x1F,
    "u": 0x20,
    "i": 0x22,
    "p": 0x23,
    "l": 0x25,
    "j": 0x26,
    "k": 0x28,
    "n": 0x2D,
    "m": 0x2E,
    "space": 0x31,
    "enter": 0x24,
    "return": 0x24,
    "tab": 0x30,
    "esc": 0x35,
    "escape": 0x35,
}
_MAC_VK_TO_KEY = {}
for _name, _code in _MAC_ANSI_VK.items():
    _MAC_VK_TO_KEY.setdefault(_code, _name)


@dataclass(frozen=True)
class HotkeySpec:
    modifiers: frozenset[str]
    key: str
    mac_vk: int | None


@dataclass(frozen=True)
class HotkeyRecordResult:
    kind: str
    spec: str | None = None
    error: str | None = None


class HotkeyMatcher:
    def __init__(self) -> None:
        self._pressed: set[str] = set()
        self._bindings: list[tuple[HotkeySpec, Callable[[], None]]] = []

    def bind(self, spec: HotkeySpec, callback: Callable[[], None]) -> None:
        self._bindings.append((spec, callback))

    def press(self, key: object) -> None:
        name = modifier_name(key)
        if name is not None:
            self._pressed.add(name)
            return
        vk = getattr(key, "vk", None)
        char = getattr(key, "char", None)
        char = char.lower() if isinstance(char, str) else None
        pressed = frozenset(self._pressed)
        for spec, callback in self._bindings:
            if spec.modifiers != pressed:
                continue
            if spec.mac_vk is not None and vk == spec.mac_vk:
                callback()
                return
            if char is not None and char == spec.key:
                callback()
                return

    def release(self, key: object) -> None:
        name = modifier_name(key)
        if name is not None:
            self._pressed.discard(name)


def parse_hotkey(spec: str) -> HotkeySpec:
    parts = [part.strip().lower() for part in spec.split("+") if part.strip()]
    if not parts:
        raise ValueError("hotkey must not be empty")
    modifiers: list[str] = []
    for part in parts[:-1]:
        name = _MODIFIER_NAMES.get(part)
        if name is None:
            raise ValueError("hotkey modifiers are invalid")
        modifiers.append(name)
    key = parts[-1]
    if key in _MODIFIER_NAMES:
        raise ValueError("hotkey must end with a key")
    if not modifiers:
        raise ValueError("hotkey must include a modifier")
    return HotkeySpec(frozenset(modifiers), key, _MAC_ANSI_VK.get(key))


def format_hotkey_spec(spec: HotkeySpec) -> str:
    parts = [name for name in _MODIFIER_ORDER if name in spec.modifiers]
    parts.append(spec.key)
    return "+".join(parts)


def display_hotkey(spec: str) -> str:
    parsed = parse_hotkey(spec)
    return (
        "".join(mark for name, mark in _DISPLAY_MARKS if name in parsed.modifiers)
        + parsed.key.upper()
    )


def hotkey_button_title(spec: str, *, recording: bool) -> str:
    if recording:
        return RECORDING_PROMPT
    return display_hotkey(spec)


def interpret_hotkey_press(*, key_code: int, modifier_flags: int) -> HotkeyRecordResult:
    if key_code == _MAC_ESCAPE_KEY_CODE:
        return HotkeyRecordResult("cancel")
    if key_code in _MAC_MODIFIER_KEY_CODES:
        return HotkeyRecordResult("ignore")
    name = _MAC_VK_TO_KEY.get(key_code)
    if name is None:
        return HotkeyRecordResult("invalid", error="不支持这个按键")
    modifiers = modifiers_from_mac_flags(modifier_flags)
    if not modifiers:
        return HotkeyRecordResult("invalid", error="快捷键必须带修饰键")
    spec = HotkeySpec(modifiers, name, _MAC_ANSI_VK.get(name))
    return HotkeyRecordResult("captured", spec=format_hotkey_spec(spec))


def modifiers_from_mac_flags(flags: int) -> frozenset[str]:
    found: list[str] = []
    if flags & _MAC_FLAG_CONTROL:
        found.append("ctrl")
    if flags & _MAC_FLAG_OPTION:
        found.append("alt")
    if flags & _MAC_FLAG_SHIFT:
        found.append("shift")
    if flags & _MAC_FLAG_COMMAND:
        found.append("cmd")
    return frozenset(found)


def to_pynput_hotkey(spec: str) -> str:
    parts = [part.strip().lower() for part in spec.split("+") if part.strip()]
    if not parts:
        raise ValueError("hotkey must not be empty")
    converted: list[str] = []
    for part in parts:
        name = _MODIFIER_NAMES.get(part)
        converted.append(_PYNPUT_MODIFIERS[name] if name is not None else part)
    if converted[-1].startswith("<") and converted[-1].endswith(">"):
        raise ValueError("hotkey must end with a key")
    if len(converted) == 1:
        raise ValueError("hotkey must include a modifier")
    return "+".join(converted)


def modifier_name(key: object) -> str | None:
    name = getattr(key, "name", None)
    if not isinstance(name, str):
        return None
    return _MODIFIER_NAMES.get(name.lower())
