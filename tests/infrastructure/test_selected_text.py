import subprocess
import traceback

import pytest

from ai_translate.core.errors import SelectionReadError
from ai_translate.infrastructure import selected_text
from ai_translate.infrastructure.selected_text import (
    EMPTY_SENTINEL,
    MAX_SELECTION_CHARS,
    SelectedTextSource,
)


class _Clipboard:
    def __init__(self, initial: str) -> None:
        self.value = initial
        self.history: list[str] = [initial]

    def read(self) -> str:
        return self.value

    def write(self, text: str) -> None:
        self.value = text
        self.history.append(text)


def test_selected_text_restores_clipboard_and_returns_copy() -> None:
    clipboard = _Clipboard("previous")

    def copy_selection() -> None:
        clipboard.write("Hello world")

    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=copy_selection,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: True,
    )
    assert source.read_selected_text() == "Hello world"
    assert clipboard.value == "previous"
    assert EMPTY_SENTINEL in clipboard.history


def test_selected_text_empty_when_copy_does_not_change_sentinel() -> None:
    clipboard = _Clipboard("previous")

    def copy_selection() -> None:
        return None

    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=copy_selection,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: True,
    )
    assert source.read_selected_text() == ""
    assert clipboard.value == "previous"


def test_selected_text_can_fall_back_to_saved_clipboard_on_windows() -> None:
    clipboard = _Clipboard("manually copied")
    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=lambda: None,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: True,
        fallback_to_saved_clipboard=True,
    )
    assert source.read_selected_text() == "manually copied"
    assert clipboard.value == "manually copied"


def test_selected_text_can_fall_back_when_copy_injection_fails() -> None:
    clipboard = _Clipboard("manually copied")

    def fail_copy() -> None:
        raise SelectionReadError("copy_simulation_failed")

    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=fail_copy,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: True,
        fallback_to_saved_clipboard=True,
    )
    assert source.read_selected_text() == "manually copied"
    assert clipboard.value == "manually copied"


def test_selected_text_rejects_stale_saved_clipboard_on_windows() -> None:
    clipboard = _Clipboard("stale clipboard")

    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=lambda: None,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: True,
        fallback_to_saved_clipboard=True,
        can_use_saved_clipboard=lambda: False,
    )

    try:
        source.read_selected_text()
        raise AssertionError("expected SelectionReadError")
    except SelectionReadError as exc:
        assert exc.code == "copy_simulation_failed"
    assert clipboard.value == "stale clipboard"


def test_selected_text_uses_clipboard_when_copy_cannot_be_simulated() -> None:
    clipboard = _Clipboard("already copied")
    calls = {"n": 0}

    def copy_selection() -> None:
        calls["n"] += 1
        raise AssertionError("copy must not run without accessibility")

    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=copy_selection,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: False,
    )
    assert source.read_selected_text() == "already copied"
    assert calls["n"] == 0
    assert clipboard.history == ["already copied"]


def test_selected_text_requires_accessibility_when_clipboard_empty() -> None:
    clipboard = _Clipboard("   ")
    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=lambda: None,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: False,
    )
    try:
        source.read_selected_text()
        raise AssertionError("expected SelectionReadError")
    except SelectionReadError as exc:
        assert exc.code == "accessibility_required"


def test_selected_text_rejects_overlong_selection() -> None:
    clipboard = _Clipboard("previous")

    def copy_selection() -> None:
        clipboard.write("x" * (MAX_SELECTION_CHARS + 1))

    source = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=copy_selection,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: True,
    )
    try:
        source.read_selected_text()
        raise AssertionError("expected SelectionReadError")
    except SelectionReadError as exc:
        assert exc.code == "selection_too_long"
    assert clipboard.value == "previous"


@pytest.mark.parametrize(
    ("operation", "code"),
    [
        ("read_clipboard", "clipboard_read_failed"),
        ("write_clipboard", "clipboard_write_failed"),
        ("send_copy_key", "copy_simulation_failed"),
    ],
)
@pytest.mark.parametrize(
    "fault_type", ["launch", "timeout", "decode", "encode"],
)
def test_selection_command_exceptions_use_stable_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    operation: str,
    code: str,
    fault_type: str,
) -> None:
    faults = {
        "launch": OSError("synthetic command failure"),
        "timeout": subprocess.TimeoutExpired("synthetic-command", 2),
        "decode": UnicodeDecodeError("utf-8", b"\xff", 0, 1, "synthetic decode failure"),
        "encode": UnicodeEncodeError("utf-8", "\ud800", 0, 1, "synthetic encode failure"),
    }

    def fail_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise faults[fault_type]

    monkeypatch.setattr(selected_text.subprocess, "run", fail_run)
    monkeypatch.setattr(selected_text, "_wait_modifiers_released", lambda: None)
    monkeypatch.setattr(selected_text, "_post_command_c", lambda: False)

    with pytest.raises(SelectionReadError) as raised:
        if operation == "write_clipboard":
            selected_text.write_clipboard("synthetic text")
        else:
            getattr(selected_text, operation)()

    assert raised.value.code == code
    assert str(raised.value) == code
    diagnostics = "".join(traceback.format_exception(raised.value))
    assert str(faults[fault_type]) not in diagnostics
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("operation", "code", "timeout"),
    [
        ("read_clipboard", "clipboard_read_failed", 2),
        ("write_clipboard", "clipboard_write_failed", 2),
        ("send_copy_key", "copy_simulation_failed", 5),
    ],
)
@pytest.mark.parametrize("returncode", [0, 1], ids=["success", "nonzero"])
def test_selection_command_exit_paths_remain_bounded(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    code: str,
    timeout: int,
    returncode: int,
) -> None:
    calls: list[dict[str, object]] = []

    def run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs)
        return subprocess.CompletedProcess([], returncode, "synthetic text", "")

    monkeypatch.setattr(selected_text.subprocess, "run", run)
    monkeypatch.setattr(selected_text, "_wait_modifiers_released", lambda: None)
    monkeypatch.setattr(selected_text, "_post_command_c", lambda: False)

    def invoke() -> str | None:
        if operation == "write_clipboard":
            return selected_text.write_clipboard("synthetic text")
        return getattr(selected_text, operation)()

    if returncode:
        with pytest.raises(SelectionReadError, match=f"^{code}$"):
            invoke()
    else:
        result = invoke()
        assert result == ("synthetic text" if operation == "read_clipboard" else None)
    assert len(calls) == 1
    assert calls[0]["timeout"] == timeout


def test_successful_quartz_copy_does_not_run_system_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_run(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Quartz copy must not run osascript")

    monkeypatch.setattr(selected_text.subprocess, "run", unexpected_run)
    monkeypatch.setattr(selected_text, "_wait_modifiers_released", lambda: None)
    monkeypatch.setattr(selected_text, "_post_command_c", lambda: True)
    selected_text.send_copy_key()
