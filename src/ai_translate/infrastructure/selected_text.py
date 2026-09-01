from __future__ import annotations

import subprocess
import time
from collections.abc import Callable

from ai_translate.core.errors import SelectionReadError

EMPTY_SENTINEL = "⟦ai-translate-empty⟧"
MAX_SELECTION_CHARS = 8000
COPY_WAIT_SECONDS = 0.45
MODIFIER_WAIT_SECONDS = 0.8
_MAC_VK_C = 0x08


def read_clipboard() -> str:
    completed = subprocess.run(
        ["pbpaste"],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    if completed.returncode != 0:
        raise SelectionReadError("clipboard_read_failed")
    return completed.stdout


def write_clipboard(text: str) -> None:
    completed = subprocess.run(
        ["pbcopy"],
        input=text,
        text=True,
        timeout=2,
        check=False,
    )
    if completed.returncode != 0:
        raise SelectionReadError("clipboard_write_failed")


def accessibility_trusted() -> bool:
    try:
        import HIServices

        return bool(HIServices.AXIsProcessTrusted())
    except Exception:
        return False


def request_accessibility_prompt() -> bool:
    try:
        import HIServices

        options = {"AXTrustedCheckOptionPrompt": True}
        return bool(HIServices.AXIsProcessTrustedWithOptions(options))
    except Exception:
        return accessibility_trusted()


def send_copy_key() -> None:
    _wait_modifiers_released()
    if _post_command_c():
        return
    completed = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "c" using command down',
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if completed.returncode != 0:
        raise SelectionReadError("copy_simulation_failed")


def _wait_modifiers_released(*, timeout: float = MODIFIER_WAIT_SECONDS) -> None:
    try:
        from Quartz import (
            CGEventSourceFlagsState,
            kCGEventFlagMaskAlternate,
            kCGEventFlagMaskCommand,
            kCGEventFlagMaskControl,
            kCGEventFlagMaskShift,
            kCGEventSourceStateHIDSystemState,
        )
    except Exception:
        time.sleep(0.15)
        return
    mask = (
        kCGEventFlagMaskAlternate
        | kCGEventFlagMaskCommand
        | kCGEventFlagMaskControl
        | kCGEventFlagMaskShift
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState) & mask) == 0:
            return
        time.sleep(0.03)


def _post_command_c() -> bool:
    try:
        from Quartz import (
            CGEventCreateKeyboardEvent,
            CGEventPost,
            CGEventSetFlags,
            CGEventSourceCreate,
            kCGEventFlagMaskCommand,
            kCGHIDEventTap,
        )
    except Exception:
        return False
    try:
        from Quartz import kCGEventSourceStatePrivate as source_state
    except Exception:
        from Quartz import kCGEventSourceStateHIDSystemState as source_state
    source = CGEventSourceCreate(source_state)
    down = CGEventCreateKeyboardEvent(source, _MAC_VK_C, True)
    up = CGEventCreateKeyboardEvent(source, _MAC_VK_C, False)
    if down is None or up is None:
        return False
    CGEventSetFlags(down, kCGEventFlagMaskCommand)
    CGEventSetFlags(up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, down)
    time.sleep(0.03)
    CGEventPost(kCGHIDEventTap, up)
    return True


class SelectedTextSource:
    def __init__(
        self,
        *,
        clipboard_read: Callable[[], str] = read_clipboard,
        clipboard_write: Callable[[str], None] = write_clipboard,
        copy_selection: Callable[[], None] = send_copy_key,
        wait: Callable[[float], None] = time.sleep,
        wait_seconds: float = COPY_WAIT_SECONDS,
        can_simulate_copy: Callable[[], bool] | None = None,
        fallback_to_saved_clipboard: bool = False,
        can_use_saved_clipboard: Callable[[], bool] | None = None,
    ) -> None:
        self._read = clipboard_read
        self._write = clipboard_write
        self._copy = copy_selection
        self._wait = wait
        self._wait_seconds = wait_seconds
        self._can_simulate_copy = can_simulate_copy or accessibility_trusted
        self._fallback_to_saved_clipboard = fallback_to_saved_clipboard
        self._can_use_saved_clipboard = can_use_saved_clipboard

    def read_selected_text(self) -> str:
        if not self._can_simulate_copy():
            text = _bounded_text(self._read())
            if not text:
                raise SelectionReadError("accessibility_required")
            return text
        saved = self._read()
        fallback_allowed = self._saved_clipboard_is_current()
        try:
            self._write(EMPTY_SENTINEL)
            try:
                self._copy()
            except SelectionReadError:
                if fallback_allowed:
                    return _bounded_text(saved)
                raise
            self._wait(self._wait_seconds)
            current = self._read()
        finally:
            self._write(saved)
        if current == EMPTY_SENTINEL:
            if fallback_allowed:
                return _bounded_text(saved)
            if self._fallback_to_saved_clipboard:
                raise SelectionReadError("copy_simulation_failed")
            return ""
        return _bounded_text(current)

    def _saved_clipboard_is_current(self) -> bool:
        if not self._fallback_to_saved_clipboard:
            return False
        checker = self._can_use_saved_clipboard
        if checker is None:
            return True
        try:
            return bool(checker())
        except Exception:
            return False


def _bounded_text(value: str) -> str:
    text = value.strip()
    if len(text) > MAX_SELECTION_CHARS:
        raise SelectionReadError("selection_too_long")
    return text
