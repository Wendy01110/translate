import inspect

from ai_translate.app import _build_macos_services, _paddle_first_load_notifier


class _Presenter:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str | None]] = []

    def show_status(self, message: str, source: str | None = None) -> None:
        self.statuses.append((message, source))

    def show(self, _job) -> None:
        pass


def test_paddle_first_load_notifier_uses_desktop_presenter() -> None:
    presenter = _Presenter()

    _paddle_first_load_notifier(presenter)("PP-OCRv6_tiny")

    assert len(presenter.statuses) == 1
    message, source = presenter.statuses[0]
    assert "PP-OCRv6_tiny" in message
    assert source is None


def test_macos_input_menu_reuses_the_result_overlay_presenter() -> None:
    source = inspect.getsource(_build_macos_services)

    assert "open_input=presenter.show_input" in source
    assert "InputTranslatePresenter" not in source
    assert "presenter.configure_target_languages" in source
    assert "on_change=listener.set_target_lang" in source
    assert "presenter.set_target_language" in source
