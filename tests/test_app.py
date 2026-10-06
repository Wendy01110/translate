from dataclasses import replace
from types import SimpleNamespace

import pytest

from ai_translate.app import (
    _build_services,
    _paddle_first_load_notifier,
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


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_desktop_actions_reuse_presenter_listener_and_runtime(monkeypatch, tmp_path, platform):
    import ai_translate.app as app_module
    from ai_translate.features.ocr_translate import OcrTranslateService
    from ai_translate.features.selection import SelectionTranslateService
    from ai_translate.core.models import JobKind, JobStatus, TranslateJob
    from ai_translate.features.history import TranslationHistory
    from ai_translate.infrastructure.history import JsonHistoryStore

    settings = Settings.load(env_file=None)
    presenters = []
    settings_windows = []
    history_windows = []
    runtimes = []
    hosted = {}
    writes = []
    history = TranslationHistory(JsonHistoryStore(tmp_path / "history.json"))
    history.set_enabled(True)

    class Presenter(_Presenter):
        def __init__(self, *_args):
            super().__init__()
            self.opened = 0
            self.language = None
            self.jobs = []
            self.translation_busy = False
            presenters.append(self)

        def set_translate(self, callback):
            self.translate = callback

        def configure_target_languages(self, options, *, current, on_change):
            self.language = current
            self.change_language = on_change

        def set_target_language(self, language):
            self.language = language

        def show_input(self):
            self.opened += 1

        def show(self, job):
            self.jobs.append(job)

    class LivePresenter(_Presenter):
        def __init__(self, *_args):
            super().__init__()

        def set_stop(self, callback):
            self.stop = callback

    class Runtime:
        def __init__(self, _settings, *, on_paddle_first_load):
            self.translator = FakeTranslator()
            self.selection = SelectionTranslateService(self.translator)
            self.ocr_translate = OcrTranslateService(FakeOcrEngine(), self.translator)
            self.notify = on_paddle_first_load
            self.updated = []
            runtimes.append(self)

        def update(self, refreshed):
            self.updated.append(refreshed)

    class SettingsWindow:
        def __init__(self, *_args, load, save):
            self.load = load
            self.save = save
            self.opened = 0
            settings_windows.append(self)

        def show(self):
            self.opened += 1

    class HistoryWindow:
        def __init__(self, *args):
            self.history, self.reuse = args[-2:]
            self.opened = 0
            history_windows.append(self)

        def show(self):
            self.opened += 1

    def host(listener, **callbacks):
        hosted.update(listener=listener, **callbacks)
        return 0

    capture = SimpleNamespace(capture_region=lambda: (b"fake", "image/png"))
    monkeypatch.setattr(app_module.sys, "platform", platform)
    monkeypatch.setattr(app_module, "DesktopRuntime", Runtime)
    monkeypatch.setattr(app_module, "_desktop_history", lambda: history)
    monkeypatch.setattr("ai_translate.interfaces.history.HistoryPresenter", HistoryWindow)
    monkeypatch.setattr("ai_translate.interfaces.history.WindowsHistoryPresenter", HistoryWindow)
    monkeypatch.setattr("ai_translate.infrastructure.selected_text.SelectedTextSource", lambda **_kwargs: SimpleNamespace(read_selected_text=lambda: "synthetic"))
    monkeypatch.setattr(app_module, "upsert_env_values", lambda path, values: writes.append((path, values)))
    monkeypatch.setattr(app_module, "resolve_env_path", lambda: "fake.env")
    if platform == "darwin":
        monkeypatch.setattr("ai_translate.interfaces.overlay.OverlayPresenter", Presenter)
        monkeypatch.setattr("ai_translate.interfaces.live_overlay.LiveOverlayPresenter", LivePresenter)
        monkeypatch.setattr("ai_translate.interfaces.settings.SettingsPresenter", SettingsWindow)
        monkeypatch.setattr("ai_translate.infrastructure.screenshot.RegionScreenshot", lambda: capture)
        monkeypatch.setattr("ai_translate.infrastructure.screenshot.RectCapture", lambda: SimpleNamespace(capture_rect=lambda _rect: (b"fake", "image/png")))
        monkeypatch.setattr("ai_translate.interfaces.region_picker.RegionPicker", lambda: object())
        monkeypatch.setattr("ai_translate.interfaces.menubar.run_status_app", host)
    else:
        monkeypatch.setattr("ai_translate.interfaces.windows_qt.WindowsOverlayPresenter", Presenter)
        monkeypatch.setattr("ai_translate.interfaces.windows_qt.WindowsLiveOverlayPresenter", LivePresenter)
        monkeypatch.setattr("ai_translate.interfaces.windows_qt.WindowsSettingsPresenter", SettingsWindow)
        monkeypatch.setattr("ai_translate.interfaces.windows_qt.WindowsUiRuntime", lambda: SimpleNamespace(run=lambda: None))
        monkeypatch.setattr("ai_translate.interfaces.windows_qt.WindowsRegionPicker", lambda _runtime: object())
        monkeypatch.setattr("ai_translate.infrastructure.windows_desktop.WindowsClipboard", lambda: SimpleNamespace(read=lambda: "", write=lambda _value: None))
        monkeypatch.setattr("ai_translate.infrastructure.windows_desktop.WindowsRectCapture", lambda: SimpleNamespace(capture_rect=lambda _rect: (b"fake", "image/png")))
        monkeypatch.setattr("ai_translate.infrastructure.windows_desktop.WindowsRegionScreenshot", lambda **_kwargs: capture)
        monkeypatch.setattr("ai_translate.infrastructure.windows_desktop.WindowsInstanceLock", lambda: SimpleNamespace(acquire=lambda: True, close=lambda: None))
        monkeypatch.setattr("ai_translate.interfaces.windows_qt.run_windows_status_app", host)

    services = app_module._build_services(settings, ["app"])
    assert services.start_app() == 0
    listener = hosted["listener"]
    presenter = presenters[0]
    runtime = runtimes[0]
    assert len(presenters) == len(runtimes) == len(settings_windows) == 1
    assert listener._presenter is presenter
    assert presenter.translate.__self__ is listener
    assert presenter.change_language.__self__ is listener
    hosted["open_input"]()
    hosted["open_settings"]()
    hosted["open_history"]()
    assert presenter.opened == settings_windows[0].opened == history_windows[0].opened == 1
    presenter.change_language("ja")
    assert listener.target_lang == "ja"
    assert presenter.translate("synthetic").translated_text == "你好"
    assert runtime.translator.calls[-1].target_lang == "ja"
    assert len(history.state.entries) == 1
    history.record(TranslateJob(JobKind.OCR, JobStatus.SUCCESS, "saved", "保存"), "en", "zh")
    request_count = len(runtime.translator.calls)
    listener._busy.acquire()
    try:
        assert history_windows[0].reuse(history.state.entries[0]) is False
        assert presenter.jobs == []
        assert listener.target_lang == "ja"
    finally:
        listener._busy.release()
    presenter.translation_busy = True
    assert history_windows[0].reuse(history.state.entries[0]) is False
    assert presenter.jobs == []
    assert listener.target_lang == "ja"
    presenter.translation_busy = False
    history_windows[0].reuse(history.state.entries[0])
    assert presenter.jobs[-1].ocr_text == "saved"
    assert presenter.language == listener.target_lang == "zh"
    assert len(runtime.translator.calls) == request_count
    assert len(history.state.entries) == 2
    runtime.notify("PP-OCRv6_tiny")
    assert len(presenter.statuses) == 1
    listener._live_running = True
    runtime.notify("PP-OCRv6_tiny")
    assert listener._live_presenter.statuses == [("本地 OCR 首次加载中，请稍候…", None)]
    refreshed = Settings.load(env_file=None)
    refreshed.translate = refreshed.translate.model_copy(update={"target_lang": "ko"})
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls: refreshed))
    settings_windows[0].save(refreshed.preferences())
    assert writes[0][0] == "fake.env"
    assert writes[0][1]["TRANSLATE_TARGET_LANG"] == "ko"
    assert runtime.updated == [refreshed]
    assert presenter.language == listener.target_lang == "ko"
