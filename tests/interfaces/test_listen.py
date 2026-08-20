from ai_translate.core.errors import ImageSourceError, SelectionReadError
from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.features.ocr_translate import OcrTranslateService
from ai_translate.features.selection import SelectionTranslateService
from ai_translate.interfaces.listen import DesktopListener
from tests.support import FakeOcrEngine, FakeTranslator


class _Presenter:
    def __init__(self) -> None:
        self.statuses: list[str] = []
        self.sources: list[str | None] = []
        self.jobs: list[TranslateJob] = []

    def show_status(self, message: str, source: str | None = None) -> None:
        self.statuses.append(message)
        self.sources.append(source)

    def show(self, job: TranslateJob) -> None:
        self.jobs.append(job)


def _listener(**overrides: object) -> tuple[DesktopListener, _Presenter]:
    presenter = _Presenter()
    payload = {
        "selection": SelectionTranslateService(FakeTranslator(translated_text="你好")),
        "ocr_translate": OcrTranslateService(
            FakeOcrEngine(text="Hello"),
            FakeTranslator(translated_text="你好"),
        ),
        "read_selected_text": lambda: "Hello",
        "capture_region": lambda: (b"png", "image/png"),
        "presenter": presenter,
        "selection_hotkey": "alt+e",
        "ocr_hotkey": "alt+w",
        "source_lang": "auto",
        "target_lang": "zh",
    }
    payload.update(overrides)
    return DesktopListener(**payload), presenter


def test_selection_hotkey_translates_selected_text() -> None:
    listener, presenter = _listener()
    listener.handle_selection()
    assert presenter.statuses == ["translating"]
    assert presenter.sources == ["Hello"]
    assert presenter.jobs[0].kind is JobKind.SELECTION
    assert presenter.jobs[0].translated_text == "你好"


def test_selection_hotkey_empty_text_does_not_call_translator() -> None:
    translator = FakeTranslator()
    listener, presenter = _listener(
        selection=SelectionTranslateService(translator),
        read_selected_text=lambda: "",
    )
    listener.handle_selection()
    assert translator.calls == []
    assert presenter.statuses == []
    assert presenter.jobs[0].error == "empty_text"


def test_ocr_hotkey_cancelled_screenshot_does_not_call_ocr() -> None:
    ocr = FakeOcrEngine()

    def capture_region() -> tuple[bytes, str]:
        raise ImageSourceError("screenshot_cancelled")

    listener, presenter = _listener(
        ocr_translate=OcrTranslateService(ocr, FakeTranslator()),
        capture_region=capture_region,
    )
    listener.handle_ocr()
    assert ocr.calls == []
    assert presenter.jobs == []


def test_present_error_shows_failure_on_overlay() -> None:
    listener, presenter = _listener()
    listener.present_error("设置页打不开：missing window")
    assert presenter.jobs[0].status is JobStatus.FAILURE
    assert presenter.jobs[0].error == "设置页打不开：missing window"


def test_selection_read_error_is_shown() -> None:
    def read_selected_text() -> str:
        raise SelectionReadError("copy_simulation_failed")

    listener, presenter = _listener(read_selected_text=read_selected_text)
    listener.handle_selection()
    assert presenter.jobs[0].status is JobStatus.FAILURE
    assert presenter.jobs[0].error == "copy_simulation_failed"


def test_run_passes_configured_hotkey_strings() -> None:
    captured: dict[str, object] = {}

    class _FakeHotkeys:
        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    def factory(mapping: dict[str, object]) -> _FakeHotkeys:
        captured.update(mapping)
        return _FakeHotkeys()

    def boom() -> None:
        raise KeyboardInterrupt

    listener, _ = _listener(hotkey_factory=factory, event_loop=boom)
    assert listener.run() == 0
    assert "alt+e" in captured
    assert "alt+w" in captured


def test_run_shows_accessibility_reminder_when_untrusted() -> None:
    class _FakeHotkeys:
        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    def boom() -> None:
        raise KeyboardInterrupt

    listener, presenter = _listener(
        hotkey_factory=lambda _mapping: _FakeHotkeys(),
        event_loop=boom,
        accessibility_ready=lambda: False,
    )
    assert listener.run() == 0
    assert presenter.jobs[0].error == "accessibility_required"


def test_run_stops_on_keyboard_interrupt() -> None:
    class _FakeHotkeys:
        def __init__(self) -> None:
            self.started = 0
            self.stopped = 0

        def start(self) -> None:
            self.started += 1

        def stop(self) -> None:
            self.stopped += 1

    fake = _FakeHotkeys()

    def boom() -> None:
        raise KeyboardInterrupt

    listener, _ = _listener(
        hotkey_factory=lambda _mapping: fake,
        event_loop=boom,
    )
    assert listener.run() == 0
    assert fake.started == 1
    assert fake.stopped == 1


def test_replace_runtime_updates_ocr_service_and_hotkeys() -> None:
    class _FakeHotkeys:
        def __init__(self) -> None:
            self.started = 0
            self.stopped = 0
            self.mapping: dict[str, object] = {}

        def start(self) -> None:
            self.started += 1

        def stop(self) -> None:
            self.stopped += 1

    created: list[_FakeHotkeys] = []

    def factory(mapping: dict[str, object]) -> _FakeHotkeys:
        fake = _FakeHotkeys()
        fake.mapping = mapping
        created.append(fake)
        return fake

    listener, _ = _listener(hotkey_factory=factory)
    started = factory(
        {
            "alt+e": listener.handle_selection,
            "alt+w": listener.handle_ocr,
        }
    )
    started.start()
    listener._hotkeys = started
    replacement = OcrTranslateService(
        FakeOcrEngine(text="Other"),
        FakeTranslator(translated_text="别的"),
    )
    listener.replace_runtime(
        selection=listener._selection,
        ocr_translate=replacement,
        source_lang="en",
        target_lang="ja",
        selection_hotkey="alt+a",
        ocr_hotkey="alt+s",
    )
    assert listener._ocr_translate is replacement
    assert listener.selection_hotkey == "alt+a"
    assert started.stopped == 1
    assert created[-1].mapping.keys() >= {"alt+a", "alt+s"}


def test_typed_text_reuses_selection_translator() -> None:
    translator = FakeTranslator(translated_text="你好")
    listener, presenter = _listener(
        selection=SelectionTranslateService(translator),
    )
    job = listener.handle_typed_text("Hello")
    assert job.status is JobStatus.SUCCESS
    assert job.translated_text == "你好"
    assert translator.calls[0].text == "Hello"
    assert presenter.jobs == []


def test_typed_text_empty_does_not_call_translator() -> None:
    translator = FakeTranslator()
    listener, _ = _listener(selection=SelectionTranslateService(translator))
    job = listener.handle_typed_text("   ")
    assert job.error == "empty_text"
    assert translator.calls == []


def test_typed_text_busy_lock_returns_busy() -> None:
    translator = FakeTranslator(translated_text="你好")
    listener, _ = _listener(selection=SelectionTranslateService(translator))
    listener._busy.acquire()
    job = listener.handle_typed_text("Hello")
    listener._busy.release()
    assert job.error == "busy"
    assert translator.calls == []


def test_busy_lock_ignores_second_trigger() -> None:
    started = {"n": 0}

    def read_selected_text() -> str:
        started["n"] += 1
        return "Hello"

    listener, presenter = _listener(read_selected_text=read_selected_text)
    listener._busy.acquire()
    listener.handle_selection()
    listener._busy.release()
    assert started["n"] == 0
    assert presenter.jobs == []
