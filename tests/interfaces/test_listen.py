import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from ai_translate.core.errors import ImageSourceError, SelectionReadError
from ai_translate.core.models import JobKind, JobStatus, ScreenRect, TranslateJob
from ai_translate.features.ocr_translate import (
    LIVE_STOPPED,
    LiveOcrMemory,
    OcrTranslateService,
)
from ai_translate.features.selection import SelectionTranslateService
from ai_translate.infrastructure import selected_text
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


@pytest.mark.parametrize(
    ("stage", "code"),
    [
        ("saved_read", "clipboard_read_failed"),
        ("selection_read", "clipboard_read_failed"),
        ("sentinel_write", "clipboard_write_failed"),
        ("restore_write", "clipboard_write_failed"),
        ("copy", "copy_simulation_failed"),
    ],
)
@pytest.mark.parametrize("fault_type", ["launch", "timeout"])
def test_selection_command_failure_is_presented_and_next_hotkey_can_retry(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    code: str,
    fault_type: str,
) -> None:
    clipboard = {"value": "previous"}
    read_count = 0
    failing = True

    def fail_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if fault_type == "launch":
            raise OSError("synthetic command failure")
        raise subprocess.TimeoutExpired("synthetic-command", 2)

    monkeypatch.setattr(selected_text.subprocess, "run", fail_run)
    monkeypatch.setattr(selected_text, "_wait_modifiers_released", lambda: None)
    monkeypatch.setattr(selected_text, "_post_command_c", lambda: False)

    def read() -> str:
        nonlocal read_count
        read_count += 1
        if failing and (
            stage == "saved_read" or (stage == "selection_read" and read_count == 2)
        ):
            return selected_text.read_clipboard()
        return clipboard["value"]

    def write(text: str) -> None:
        if failing and (
            (stage == "sentinel_write" and text == selected_text.EMPTY_SENTINEL)
            or (stage == "restore_write" and text == "previous")
        ):
            selected_text.write_clipboard(text)
        clipboard["value"] = text

    def copy() -> None:
        if failing and stage == "copy":
            selected_text.send_copy_key()
        clipboard["value"] = "Hello"

    source = selected_text.SelectedTextSource(
        clipboard_read=read,
        clipboard_write=write,
        copy_selection=copy,
        wait=lambda _seconds: None,
        can_simulate_copy=lambda: True,
    )
    translator = FakeTranslator(translated_text="你好")
    listener, presenter = _listener(
        selection=SelectionTranslateService(translator),
        read_selected_text=source.read_selected_text,
    )

    listener.handle_selection()

    assert translator.calls == []
    assert presenter.statuses == []
    assert len(presenter.jobs) == 1
    job = presenter.jobs[0]
    assert job.kind is JobKind.SELECTION
    assert job.status is JobStatus.FAILURE
    assert job.error == code
    assert job.source_text is None
    assert job.translated_text is None
    assert clipboard["value"] == ("Hello" if stage == "restore_write" else "previous")
    assert capsys.readouterr() == ("", "")

    failing = False
    saved = clipboard["value"]
    listener.handle_selection()

    assert len(translator.calls) == 1
    assert presenter.jobs[-1].status is JobStatus.SUCCESS
    assert presenter.jobs[-1].translated_text == "你好"
    assert clipboard["value"] == saved


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
    assert "alt+q" in captured


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
        live_hotkey="alt+d",
    )
    assert listener._ocr_translate is replacement
    assert listener.selection_hotkey == "alt+a"
    assert listener.live_hotkey == "alt+d"
    assert started.stopped == 1
    assert created[-1].mapping.keys() >= {"alt+a", "alt+s", "alt+d"}


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


def test_target_language_switch_applies_to_typed_text_and_resets_live_memory() -> None:
    translator = FakeTranslator(translated_text="こんにちは")
    listener, _ = _listener(selection=SelectionTranslateService(translator))
    listener._live_memory = LiveOcrMemory(frame_hash="frame", ocr_text="Hello")

    listener.set_target_lang(" JA ")
    job = listener.handle_typed_text("Hello")

    assert listener.target_lang == "ja"
    assert listener._live_memory == LiveOcrMemory()
    assert job.status is JobStatus.SUCCESS
    assert translator.calls[0].target_lang == "ja"


def test_target_language_switch_applies_to_next_ocr_translation() -> None:
    translator = FakeTranslator(translated_text="안녕하세요")
    listener, _ = _listener(
        ocr_translate=OcrTranslateService(FakeOcrEngine(text="Hello"), translator)
    )

    listener.set_target_lang("ko")
    listener.handle_ocr()

    assert translator.calls[0].target_lang == "ko"


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


def _live_listener(**overrides: object) -> tuple[DesktopListener, _Presenter]:
    ocr = overrides.pop("ocr", FakeOcrEngine(text="Hello"))
    translator = overrides.pop("translator", FakeTranslator(translated_text="你好"))
    payload = {
        "ocr_translate": OcrTranslateService(ocr, translator),
        "pick_region": lambda: ScreenRect(x=10, y=20, width=80, height=40),
        "capture_rect": lambda _rect: (b"frame-a", "image/png"),
        "hash_image": lambda data: data.decode(),
        "live_interval_seconds": 30.0,
    }
    payload.update(overrides)
    return _listener(**payload)


class _AsyncPicker:
    needs_main_thread = False

    def __init__(self) -> None:
        self.callback = None
        self.cancelled = 0

    def start(self, callback) -> None:
        self.callback = callback

    def complete(self, rect: ScreenRect | None) -> None:
        callback = self.callback
        self.callback = None
        if callback is not None:
            callback(rect)

    def cancel(self) -> None:
        self.cancelled += 1
        self.complete(None)


@pytest.fixture
def _fake_live_workers(monkeypatch):
    workers: list[object] = []

    class Worker:
        def __init__(self, **_kwargs) -> None:
            pass

        def start(self) -> None:
            workers.append(self)

    monkeypatch.setattr("ai_translate.interfaces.listen.threading.Thread", Worker)
    return workers


class _StopOnFirstWait:
    def __init__(self) -> None:
        self.waits: list[float] = []

    def is_set(self) -> bool:
        return False

    def wait(self, seconds: float) -> bool:
        self.waits.append(seconds)
        return True


def test_live_tick_skips_unchanged_frame_without_second_ocr() -> None:
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator(translated_text="你好")
    listener, presenter = _live_listener(ocr=ocr, translator=translator)
    listener._live_rect = ScreenRect(x=10, y=20, width=80, height=40)
    listener._live_stop.clear()
    listener._live_running = True
    assert listener.live_tick() == "show"
    assert listener.live_tick() == "skip_frame"
    assert len(ocr.calls) == 1
    assert len(translator.calls) == 1
    assert presenter.jobs[0].translated_text == "你好"


def test_live_hotkey_toggles_start_and_stop() -> None:
    listener, presenter = _live_listener()
    listener.handle_live_ocr()
    assert listener.live_running is True
    assert presenter.statuses[-1] == "识别中…"
    listener.handle_live_ocr()
    assert listener.live_running is False


def test_live_cancel_pick_does_not_capture() -> None:
    captured: list[ScreenRect] = []
    listener, presenter = _live_listener(
        pick_region=lambda: None,
        capture_rect=lambda rect: captured.append(rect) or (b"png", "image/png"),
    )
    listener.handle_live_ocr()
    assert listener.live_running is False
    assert captured == []
    assert presenter.jobs == []


def test_async_live_picker_does_not_start_loop_until_selection_finishes() -> None:
    picker = _AsyncPicker()
    listener, presenter = _live_listener(pick_region=picker)
    listener.handle_live_ocr()

    assert listener._live_starting is True
    assert listener.live_running is False
    assert presenter.statuses == []

    picker.complete(ScreenRect(x=10, y=20, width=80, height=40))

    assert listener._live_starting is False
    assert listener.live_running is True
    assert presenter.statuses[-1] == "识别中…"
    listener.stop_live()


def test_live_hotkey_cancels_open_async_picker() -> None:
    picker = _AsyncPicker()
    listener, presenter = _live_listener(pick_region=picker)
    listener.handle_live_ocr()
    listener.handle_live_ocr()

    assert picker.cancelled == 1
    assert listener._live_starting is False
    assert listener.live_running is False
    assert presenter.jobs == []


@pytest.mark.parametrize("old_result", [None, ScreenRect(x=10, y=20, width=80, height=40)])
def test_old_picker_callback_cannot_affect_restarted_session(old_result, _fake_live_workers) -> None:
    picker = _AsyncPicker()
    captured: list[ScreenRect] = []
    listener, presenter = _live_listener(
        pick_region=picker,
        capture_rect=lambda rect: captured.append(rect) or (b"frame-a", "image/png"),
    )
    listener.handle_live_ocr()
    old_callback = picker.callback
    listener.stop_live()
    listener.handle_live_ocr()
    new_callback = picker.callback

    old_callback(old_result)
    assert listener._live_starting is True
    assert listener.live_running is False
    assert listener._live_rect is None
    assert presenter.statuses == []
    assert _fake_live_workers == []
    assert captured == []

    rect = ScreenRect(x=-100, y=60, width=200, height=100)
    new_callback(rect)
    new_callback(ScreenRect(x=0, y=0, width=40, height=40))
    assert listener._live_rect == rect
    assert listener.live_running is True
    assert len(_fake_live_workers) == 1
    assert presenter.statuses == ["识别中…"]
    assert listener.live_tick() == "show"
    assert captured == [rect]
    listener.stop_live()


def test_queued_old_picker_start_is_discarded(monkeypatch, _fake_live_workers) -> None:
    queued: list[object] = []
    helper = SimpleNamespace(callAfter=queued.append)
    monkeypatch.setitem(sys.modules, "Foundation", SimpleNamespace(
        NSThread=SimpleNamespace(isMainThread=lambda: False),
    ))
    monkeypatch.setitem(sys.modules, "PyObjCTools", SimpleNamespace(AppHelper=helper))
    monkeypatch.setitem(sys.modules, "PyObjCTools.AppHelper", helper)
    picker = _AsyncPicker()
    picker.needs_main_thread = True
    listener, presenter = _live_listener(pick_region=picker)
    listener.handle_live_ocr()
    listener.stop_live()
    listener.handle_live_ocr()
    assert len(queued) == 2

    queued[0]()
    assert picker.callback is None
    assert listener._live_starting is True
    queued[1]()
    assert callable(picker.callback)
    picker.complete(ScreenRect(x=10, y=20, width=80, height=40))
    assert listener.live_running is True
    assert len(_fake_live_workers) == 1
    assert presenter.statuses == ["识别中…"]
    listener.stop_live()


def test_old_picker_start_failure_cannot_clear_new_session(monkeypatch, _fake_live_workers) -> None:
    picker = _AsyncPicker()
    listener, _presenter = _live_listener(pick_region=picker)
    original_start = picker.start
    first_start = [True]

    def start(callback):
        original_start(callback)
        if first_start[0]:
            first_start[0] = False
            listener.stop_live()
            listener.handle_live_ocr()
            raise RuntimeError("Synthetic picker failure")

    monkeypatch.setattr(picker, "start", start)
    with pytest.raises(RuntimeError, match="Synthetic picker failure"):
        listener.handle_live_ocr()
    assert listener._live_starting is True
    assert _fake_live_workers == []
    picker.complete(ScreenRect(x=10, y=20, width=80, height=40))
    assert listener.live_running is True
    assert len(_fake_live_workers) == 1
    listener.stop_live()


@pytest.mark.parametrize("asynchronous", [False, True])
def test_current_picker_start_failure_allows_retry(monkeypatch, asynchronous, _fake_live_workers) -> None:
    def fail(*_args):
        raise RuntimeError("Synthetic picker failure")

    picker = _AsyncPicker() if asynchronous else fail
    if asynchronous:
        monkeypatch.setattr(picker, "start", fail)
    listener, presenter = _live_listener(pick_region=picker)
    with pytest.raises(RuntimeError, match="Synthetic picker failure"):
        listener.handle_live_ocr()
    assert listener._live_starting is False
    assert listener.live_running is False
    assert presenter.statuses == []
    assert _fake_live_workers == []

    listener._pick_region = lambda: ScreenRect(x=10, y=20, width=80, height=40)
    listener.handle_live_ocr()
    assert listener.live_running is True
    assert len(_fake_live_workers) == 1
    listener.stop_live()


def test_stop_during_live_start_status_does_not_start_worker(monkeypatch, _fake_live_workers) -> None:
    listener, presenter = _live_listener()

    def stop_on_status(_message, source=None):
        listener.stop_live()

    monkeypatch.setattr(presenter, "show_status", stop_on_status)
    listener.handle_live_ocr()
    assert listener.live_running is False
    assert _fake_live_workers == []


def test_one_shot_ocr_is_ignored_while_live_runs() -> None:
    ocr = FakeOcrEngine(text="Hello")
    listener, presenter = _live_listener(ocr=ocr)
    listener._live_running = True
    listener.handle_ocr()
    assert presenter.jobs == []
    assert ocr.calls == []


def test_one_shot_ocr_is_ignored_while_live_picker_is_open() -> None:
    ocr = FakeOcrEngine(text="Hello")
    listener, presenter = _live_listener(ocr=ocr)
    listener._live_starting = True
    listener.handle_ocr()
    assert presenter.jobs == []
    assert ocr.calls == []


def test_overlapping_live_ticks_are_skipped() -> None:
    listener, _presenter = _live_listener()
    listener._live_rect = ScreenRect(x=10, y=20, width=80, height=40)
    listener._live_stop.clear()
    listener._live_running = True
    listener._live_tick_lock.acquire()
    assert listener.live_tick() is None
    listener._live_tick_lock.release()


def test_live_loop_counts_processing_time_toward_refresh_interval(monkeypatch) -> None:
    listener, _presenter = _live_listener(live_interval_seconds=0.8)
    listener._live_generation = 1
    listener._live_running = True
    stop = _StopOnFirstWait()
    listener._live_stop = stop
    timestamps = iter((10.0, 10.3))
    monkeypatch.setattr(
        "ai_translate.interfaces.listen.time.monotonic",
        lambda: next(timestamps),
    )
    monkeypatch.setattr(listener, "live_tick", lambda _generation: "show")

    listener._live_loop(1)

    assert len(stop.waits) == 1
    assert abs(stop.waits[0] - 0.5) < 1e-9


def test_live_loop_does_not_add_delay_after_slow_tick(monkeypatch) -> None:
    listener, _presenter = _live_listener(live_interval_seconds=0.8)
    listener._live_generation = 1
    listener._live_running = True
    stop = _StopOnFirstWait()
    listener._live_stop = stop
    timestamps = iter((10.0, 11.2))
    monkeypatch.setattr(
        "ai_translate.interfaces.listen.time.monotonic",
        lambda: next(timestamps),
    )
    monkeypatch.setattr(listener, "live_tick", lambda _generation: "show")

    listener._live_loop(1)

    assert stop.waits == [0.0]


def test_stop_during_capture_discards_frame_before_ocr() -> None:
    holder: dict[str, DesktopListener] = {}
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator(translated_text="你好")

    def capture(_rect: ScreenRect) -> tuple[bytes, str]:
        holder["listener"].stop_live()
        return b"frame-a", "image/png"

    listener, presenter = _live_listener(
        ocr=ocr,
        translator=translator,
        capture_rect=capture,
    )
    holder["listener"] = listener
    listener._live_rect = ScreenRect(x=10, y=20, width=80, height=40)
    listener._live_stop.clear()
    listener._live_running = True

    assert listener.live_tick() == LIVE_STOPPED
    assert ocr.calls == []
    assert translator.calls == []
    assert presenter.jobs == []


def test_stop_during_translation_discards_stale_result() -> None:
    holder: dict[str, DesktopListener] = {}
    translator = FakeTranslator(translated_text="你好")
    original_translate = translator.translate

    def translate_then_stop(request):
        result = original_translate(request)
        holder["listener"].stop_live()
        return result

    translator.translate = translate_then_stop
    listener, presenter = _live_listener(translator=translator)
    holder["listener"] = listener
    listener._live_rect = ScreenRect(x=10, y=20, width=80, height=40)
    listener._live_stop.clear()
    listener._live_running = True

    assert listener.live_tick() == LIVE_STOPPED
    assert len(translator.calls) == 1
    assert presenter.jobs == []


@pytest.mark.parametrize("stage", ["ocr", "translation"])
@pytest.mark.parametrize("switch_back", [False, True])
def test_language_switch_discards_inflight_live_work_and_next_tick_continues(
    stage: str,
    switch_back: bool,
) -> None:
    started = threading.Event()
    release = threading.Event()
    ocr = FakeOcrEngine(text="Hello")
    translator = FakeTranslator(translated_text="Synthetic translation")
    owner = ocr if stage == "ocr" else translator
    method = "recognize_pages" if stage == "ocr" else "translate"
    original = getattr(owner, method)

    def blocked_call(request):
        started.set()
        assert release.wait(3)
        return original(request)

    setattr(owner, method, blocked_call)
    listener, presenter = _live_listener(ocr=ocr, translator=translator)
    listener._live_rect = ScreenRect(x=10, y=20, width=80, height=40)
    listener._live_stop.clear()
    listener._live_running = True
    generation = listener._live_generation
    actions: list[str | None] = []
    worker = threading.Thread(
        target=lambda: actions.append(listener.live_tick()), daemon=True
    )
    worker.start()
    try:
        assert started.wait(3)
        listener.set_target_lang("ja")
        if switch_back:
            listener.set_target_lang("zh")
    finally:
        release.set()
        worker.join(3)

    assert not worker.is_alive()
    assert actions == [LIVE_STOPPED]
    assert presenter.jobs == []
    assert listener._live_memory == LiveOcrMemory()
    assert listener.live_running is True
    assert listener._live_generation == generation
    assert listener.live_tick() == "show"
    expected_target = "zh" if switch_back else "ja"
    expected_calls = [expected_target] if stage == "ocr" else ["zh", expected_target]
    assert [request.target_lang for request in translator.calls] == expected_calls
    assert len(presenter.jobs) == 1
    assert listener.live_tick() == "skip_frame"


def test_language_switch_clears_pending_retry_for_the_same_frame() -> None:
    now = [0.0]
    translator = FakeTranslator(
        translated_text=None, status=JobStatus.FAILURE, error="timeout"
    )
    listener, _ = _live_listener(
        ocr_translate=OcrTranslateService(FakeOcrEngine(), translator, clock=lambda: now[0])
    )
    listener._live_rect = ScreenRect(x=10, y=20, width=80, height=40)
    listener._live_stop.clear()
    listener._live_running = True
    assert listener.live_tick() == "show"
    assert listener.live_tick() == "skip_frame"

    listener.set_target_lang("ja")
    assert listener.live_tick() == "show"
    assert [request.target_lang for request in translator.calls] == ["zh", "ja"]


def test_replace_runtime_stops_active_live_loop() -> None:
    listener, _presenter = _live_listener()
    listener._live_rect = ScreenRect(x=10, y=20, width=80, height=40)
    listener._live_stop.clear()
    listener._live_running = True

    listener.replace_runtime(
        selection=listener._selection,
        ocr_translate=listener._ocr_translate,
        source_lang="en",
        target_lang="ja",
        selection_hotkey="alt+e",
        ocr_hotkey="alt+w",
        live_hotkey="alt+q",
    )

    assert listener.live_running is False
    assert listener._live_rect is None


def test_replace_runtime_cancels_pending_picker_and_new_session_uses_new_settings(_fake_live_workers) -> None:
    picker = _AsyncPicker()
    old_ocr = FakeOcrEngine()
    old_translator = FakeTranslator()
    listener, presenter = _live_listener(pick_region=picker, ocr=old_ocr, translator=old_translator)
    listener.handle_live_ocr()
    old_callback = picker.callback
    new_ocr = FakeOcrEngine()
    new_translator = FakeTranslator()
    listener.replace_runtime(
        selection=SelectionTranslateService(new_translator),
        ocr_translate=OcrTranslateService(new_ocr, new_translator),
        source_lang="en", target_lang="ja",
        selection_hotkey="alt+e", ocr_hotkey="alt+w", live_hotkey="alt+q",
    )
    assert picker.cancelled == 1
    assert listener._live_starting is False
    assert listener.live_running is False
    old_callback(ScreenRect(x=10, y=20, width=80, height=40))
    assert presenter.statuses == []
    assert _fake_live_workers == []

    listener.handle_live_ocr()
    picker.complete(ScreenRect(x=30, y=40, width=120, height=60))
    assert len(_fake_live_workers) == 1
    assert listener.live_tick() == "show"
    assert old_ocr.calls == []
    assert old_translator.calls == []
    assert len(new_ocr.calls) == 1
    assert [(call.source_lang, call.target_lang) for call in new_translator.calls] == [("en", "ja")]
    listener.stop_live()
