from ai_translate.core.errors import SelectionReadError
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
