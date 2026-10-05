import inspect
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ai_translate.app import (
    _build_macos_services,
    _build_services,
    _build_windows_services,
    _paddle_first_load_notifier,
    _save_preferences,
)
from ai_translate.bootstrap.composition import config_status
from ai_translate.config import Settings
from ai_translate.interfaces.cli import run
from tests.support import FakeOcrEngine, FakeTranslator


@pytest.mark.parametrize(
    ("platform", "argv", "expected_ocr", "expected_translate", "output"),
    [
        (platform, argv, expected_ocr, expected_translate, output)
        for platform in ("darwin", "win32", "linux")
        for argv, expected_ocr, expected_translate, output in (
            (["text", "app"], 0, 1, "你好"),
            (["ocr", "--image", "listen"], 1, 0, "Hello"),
            (["ocr-translate", "--image", "page.png"], 1, 1, "你好"),
        )
    ] + [
        (platform, [command, "--screenshot"], 1, expected_translate, output)
        for platform in ("darwin", "win32")
        for command, expected_translate, output in (
            ("ocr", 0, "Hello"), ("ocr-translate", 1, "你好"),
        )
    ],
)
def test_cli_constructs_only_services_used_by_the_command(
    monkeypatch, capsys, platform, argv, expected_ocr, expected_translate, output,
) -> None:
    settings = Settings.load(env_file=None)
    settings.translate = settings.translate.model_copy(
        update={"source_lang": "en", "target_lang": "ja"}
    )
    status = config_status(settings)
    engine = FakeOcrEngine()
    translator = FakeTranslator()
    constructed = {"ocr": 0, "translate": 0}

    def build_ocr(_settings, **_kwargs):
        constructed["ocr"] += 1
        return engine

    def build_translator(_settings):
        constructed["translate"] += 1
        return translator

    monkeypatch.setattr("ai_translate.app.sys.platform", platform)
    monkeypatch.setattr("ai_translate.app.ocr_engine", build_ocr)
    monkeypatch.setattr("ai_translate.bootstrap.composition.ocr_engine", build_ocr)
    monkeypatch.setattr("ai_translate.bootstrap.composition.translator_for", build_translator)
    capture_calls = []

    def capture():
        capture_calls.append(True)
        return b"png", "image/png"

    if "--screenshot" in argv:
        if platform == "darwin":
            monkeypatch.setattr(
                "ai_translate.infrastructure.screenshot.RegionScreenshot",
                lambda: SimpleNamespace(capture_region=capture),
            )
        else:
            monkeypatch.setattr("ai_translate.interfaces.windows_qt.WindowsUiRuntime", object)
            monkeypatch.setattr(
                "ai_translate.interfaces.windows_qt.WindowsRegionPicker",
                lambda _runtime: object(),
            )
            monkeypatch.setattr(
                "ai_translate.infrastructure.windows_desktop.WindowsRectCapture",
                lambda: SimpleNamespace(capture_rect=lambda _rect: (b"png", "image/png")),
            )
            monkeypatch.setattr(
                "ai_translate.infrastructure.windows_desktop.WindowsRegionScreenshot",
                lambda **_kwargs: SimpleNamespace(capture_region=capture),
            )
    services = replace(
        _build_services(settings, argv),
        load_image=lambda _path: (b"png", "image/png"),
    )

    assert run(argv, status, services) == 0
    assert capsys.readouterr().out == f"{output}\n"
    assert constructed == {"ocr": expected_ocr, "translate": expected_translate}
    assert len(engine.calls) == expected_ocr
    assert len(translator.calls) == expected_translate
    assert len(capture_calls) == int("--screenshot" in argv)
    if translator.calls:
        assert translator.calls[0].source_lang == "en"
        assert translator.calls[0].target_lang == "ja"


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


def test_paddle_first_load_notifier_uses_live_presenter_during_live_ocr() -> None:
    presenter = _Presenter()
    live_presenter = _Presenter()
    active = [False]
    notify = _paddle_first_load_notifier(
        presenter,
        live_presenter=live_presenter,
        live_active=lambda: active[0],
    )

    notify("PP-OCRv6_tiny")
    active[0] = True
    notify("PP-OCRv6_tiny")

    assert len(presenter.statuses) == 1
    assert len(live_presenter.statuses) == 1
    assert "PP-OCRv6_tiny" in presenter.statuses[0][0]
    assert live_presenter.statuses == [("本地 OCR 首次加载中，请稍候…", None)]


def test_macos_input_menu_reuses_the_result_overlay_presenter() -> None:
    source = inspect.getsource(_build_macos_services)
    save_source = inspect.getsource(_save_preferences)

    assert "open_input=presenter.show_input" in source
    assert "InputTranslatePresenter" not in source
    assert "presenter.configure_target_languages" in source
    assert "on_change=listener.set_target_lang" in source
    assert "_save_preferences(" in source
    assert "presenter.set_target_language" in save_source
    assert "live_presenter=live_ui" in source
    assert "listener and listener.live_running" in source


def test_windows_input_menu_reuses_the_result_overlay_presenter() -> None:
    source = inspect.getsource(_build_windows_services)
    save_source = inspect.getsource(_save_preferences)

    assert "open_input=presenter.show_input" in source
    assert "WindowsInputTranslatePresenter" not in source
    assert "presenter.configure_target_languages" in source
    assert "on_change=listener.set_target_lang" in source
    assert "_save_preferences(" in source
    assert "presenter.set_target_language" in save_source
    assert "live_presenter=live_ui" in source
    assert "listener and listener.live_running" in source
    assert (
        "can_use_saved_clipboard=windows_clipboard_owned_by_foreground" in source
    )
