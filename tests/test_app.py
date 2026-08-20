from ai_translate.app import _paddle_first_load_notifier


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
