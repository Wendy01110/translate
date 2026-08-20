from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable

from ai_translate.core.errors import ImageSourceError, SelectionReadError
from ai_translate.core.hotkeys import HotkeyMatcher, parse_hotkey
from ai_translate.core.models import JobKind, JobStatus, ScreenRect, TranslateJob
from ai_translate.core.ports import ResultPresenter
from ai_translate.features.ocr_translate import (
    LIVE_SHOW,
    LIVE_STOPPED,
    LiveOcrMemory,
    OcrTranslateService,
    image_signature as default_image_signature,
)
from ai_translate.features.selection import SelectionTranslateService

LIVE_OCR_INTERVAL_SECONDS = 0.8


class DesktopListener:
    def __init__(
        self,
        *,
        selection: SelectionTranslateService,
        ocr_translate: OcrTranslateService,
        read_selected_text: Callable[[], str],
        capture_region: Callable[[], tuple[bytes, str]],
        presenter: ResultPresenter,
        selection_hotkey: str,
        ocr_hotkey: str,
        source_lang: str,
        target_lang: str,
        hotkey_factory: Callable[..., object] | None = None,
        event_loop: Callable[[], None] | None = None,
        accessibility_ready: Callable[[], bool] | None = None,
        permission_prompt: Callable[[], None] | None = None,
        live_hotkey: str = "alt+q",
        pick_region: Callable[[], ScreenRect | None] | None = None,
        capture_rect: Callable[[ScreenRect], tuple[bytes, str]] | None = None,
        live_presenter: ResultPresenter | None = None,
        live_interval_seconds: float = LIVE_OCR_INTERVAL_SECONDS,
        hash_image: Callable[[bytes], str] | None = None,
    ) -> None:
        self._selection = selection
        self._ocr_translate = ocr_translate
        self._read_selected_text = read_selected_text
        self._capture_region = capture_region
        self._presenter = presenter
        self._selection_hotkey = selection_hotkey
        self._ocr_hotkey = ocr_hotkey
        self._live_hotkey = live_hotkey
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._hotkey_factory = hotkey_factory
        self._event_loop = event_loop
        self._accessibility_ready = accessibility_ready
        self._permission_prompt = permission_prompt
        self._pick_region = pick_region
        self._capture_rect = capture_rect
        self._live_presenter = live_presenter or presenter
        self._live_interval_seconds = live_interval_seconds
        self._hash_image = hash_image or default_image_signature
        self._busy = threading.Lock()
        self._hotkeys: object | None = None
        self._live_stop = threading.Event()
        self._live_stop.set()
        self._live_starting = False
        self._live_running = False
        self._live_rect: ScreenRect | None = None
        self._live_memory = LiveOcrMemory()
        self._live_tick_lock = threading.Lock()
        self._live_thread: threading.Thread | None = None
        self._live_generation = 0

    @property
    def selection_hotkey(self) -> str:
        return self._selection_hotkey

    @property
    def ocr_hotkey(self) -> str:
        return self._ocr_hotkey

    @property
    def live_hotkey(self) -> str:
        return self._live_hotkey

    @property
    def live_running(self) -> bool:
        return self._live_running

    @property
    def accessibility_ready(self) -> bool:
        if self._accessibility_ready is None:
            return True
        return bool(self._accessibility_ready())

    def handle_selection(self) -> None:
        self._run_exclusive(self._selection_job)

    def handle_ocr(self) -> None:
        if self._live_starting or self._live_running:
            return
        self._run_exclusive(self._ocr_job)

    def handle_live_ocr(self) -> None:
        if self._live_starting or self._live_running:
            self.stop_live()
            return
        if self._pick_region is None or self._capture_rect is None:
            return
        if bool(getattr(self._pick_region, "needs_main_thread", False)):
            try:
                from Foundation import NSThread
                from PyObjCTools.AppHelper import callAfter
            except Exception:
                pass
            else:
                if not NSThread.isMainThread():
                    self._live_starting = True
                    callAfter(self._start_live_pending)
                    return
        self._live_starting = True
        self._start_live_pending()

    def _start_live_pending(self) -> None:
        if not self._live_starting:
            return
        picker = self._pick_region
        if picker is None:
            self._live_starting = False
            return
        start = getattr(picker, "start", None)
        if callable(start):
            try:
                start(self._complete_live_pick)
            except Exception:
                self._live_starting = False
                raise
            return
        try:
            rect = picker()
        except Exception:
            self._live_starting = False
            raise
        self._complete_live_pick(rect)

    def stop_live(self) -> None:
        was_starting = self._live_starting
        self._live_generation += 1
        self._live_stop.set()
        self._live_starting = False
        self._live_running = False
        self._live_rect = None
        self._live_memory = LiveOcrMemory()
        hide = getattr(self._live_presenter, "hide", None)
        if callable(hide):
            hide()
        set_anchor = getattr(self._live_presenter, "set_anchor", None)
        if callable(set_anchor):
            set_anchor(None)
        if was_starting:
            cancel = getattr(self._pick_region, "cancel", None)
            if callable(cancel):
                cancel()

    def live_tick(self, generation: int | None = None) -> str | None:
        expected_generation = (
            self._live_generation if generation is None else generation
        )
        if not self._live_tick_lock.acquire(blocking=False):
            return None
        try:
            return self._live_tick_body(expected_generation)
        finally:
            self._live_tick_lock.release()

    def _complete_live_pick(self, rect: ScreenRect | None) -> None:
        if not self._live_starting:
            return
        self._live_starting = False
        capture = self._capture_rect
        if capture is None:
            return
        if rect is None or not rect.is_usable():
            return
        self._live_rect = rect.canonical()
        self._live_memory = LiveOcrMemory()
        self._live_generation += 1
        generation = self._live_generation
        self._live_stop.clear()
        self._live_running = True
        set_anchor = getattr(self._live_presenter, "set_anchor", None)
        if callable(set_anchor):
            set_anchor(self._live_rect)
        self._live_presenter.show_status("识别中…")
        thread = threading.Thread(
            target=self._live_loop,
            args=(generation,),
            daemon=True,
        )
        thread.start()
        self._live_thread = thread

    def _live_loop(self, generation: int) -> None:
        try:
            while not self._live_stop.is_set() and self._live_generation == generation:
                tick_started = time.monotonic()
                self.live_tick(generation)
                if self._live_generation != generation:
                    break
                elapsed = max(0.0, time.monotonic() - tick_started)
                wait_seconds = max(0.0, self._live_interval_seconds - elapsed)
                if self._live_stop.wait(wait_seconds):
                    break
        finally:
            if self._live_generation == generation:
                self._live_running = False

    def _live_tick_body(self, generation: int) -> str | None:
        if not self._live_is_current(generation):
            return LIVE_STOPPED
        rect = self._live_rect
        capture = self._capture_rect
        if rect is None or capture is None:
            return None
        try:
            image_bytes, mime_type = capture(rect)
        except ImageSourceError as exc:
            if not self._live_is_current(generation):
                return LIVE_STOPPED
            if exc.code == "screenshot_cancelled":
                return None
            self._live_presenter.show(
                TranslateJob(
                    kind=JobKind.OCR,
                    status=JobStatus.FAILURE,
                    source_text=None,
                    translated_text=None,
                    error=exc.code,
                )
            )
            return exc.code
        if not self._live_is_current(generation):
            return LIVE_STOPPED
        frame_hash = self._hash_image(image_bytes)
        if not self._live_is_current(generation):
            return LIVE_STOPPED
        result = self._ocr_translate.advance_live(
            image_bytes,
            mime_type,
            self._source_lang,
            self._target_lang,
            frame_hash=frame_hash,
            memory=self._live_memory,
            should_continue=lambda: self._live_is_current(generation),
        )
        if not self._live_is_current(generation):
            return LIVE_STOPPED
        self._live_memory = result.memory
        if result.action == LIVE_SHOW and result.job is not None:
            self._live_presenter.show(result.job)
        return result.action

    def _live_is_current(self, generation: int) -> bool:
        return (
            self._live_generation == generation
            and self._live_running
            and not self._live_stop.is_set()
        )

    def handle_typed_text(self, text: str) -> TranslateJob:
        if not self._busy.acquire(blocking=False):
            return TranslateJob(
                kind=JobKind.SELECTION,
                status=JobStatus.FAILURE,
                source_text=text,
                translated_text=None,
                error="busy",
            )
        try:
            return self._selection.translate_text(
                text,
                self._source_lang,
                self._target_lang,
            )
        finally:
            self._busy.release()

    def run(self) -> int:
        if sys.platform not in {"darwin", "win32"}:
            print("listen is only supported on macOS and Windows", file=sys.stderr)
            return 2
        mapping = {
            self._selection_hotkey: self.handle_selection,
            self._ocr_hotkey: self.handle_ocr,
            self._live_hotkey: self.handle_live_ocr,
        }
        factory = self._hotkey_factory or _default_hotkey_factory
        listener = factory(mapping)
        start = getattr(listener, "start", None)
        if callable(start):
            start()
        self._hotkeys = listener
        if self._accessibility_ready is not None and not self._accessibility_ready():
            warning = _accessibility_warning()
            if warning is not None:
                print(warning, file=sys.stderr)
            self._presenter.show(
                TranslateJob(
                    kind=JobKind.SELECTION,
                    status=JobStatus.FAILURE,
                    source_text=None,
                    translated_text=None,
                    error="accessibility_required",
                )
            )
            if self._permission_prompt is not None:
                self._permission_prompt()
        print(
            f"listening: selection={self._selection_hotkey} ocr={self._ocr_hotkey} live={self._live_hotkey}",
            file=sys.stderr,
        )
        loop = self._event_loop or _default_event_loop
        try:
            loop()
        except KeyboardInterrupt:
            return 0
        finally:
            self.stop_live()
            stop = getattr(self._hotkeys, "stop", None)
            if callable(stop):
                stop()
            self._hotkeys = None
        return 0

    def present_error(self, message: str) -> None:
        self._presenter.show(
            TranslateJob(
                kind=JobKind.SELECTION,
                status=JobStatus.FAILURE,
                source_text=None,
                translated_text=None,
                error=message,
            )
        )

    def replace_runtime(
        self,
        *,
        selection: SelectionTranslateService,
        ocr_translate: OcrTranslateService,
        source_lang: str,
        target_lang: str,
        selection_hotkey: str,
        ocr_hotkey: str,
        live_hotkey: str | None = None,
    ) -> None:
        if self._live_running:
            self.stop_live()
        self._selection = selection
        self._ocr_translate = ocr_translate
        self._source_lang = source_lang
        self._target_lang = target_lang
        next_live = self._live_hotkey if live_hotkey is None else live_hotkey
        hotkeys_changed = (
            selection_hotkey != self._selection_hotkey
            or ocr_hotkey != self._ocr_hotkey
            or next_live != self._live_hotkey
        )
        self._selection_hotkey = selection_hotkey
        self._ocr_hotkey = ocr_hotkey
        self._live_hotkey = next_live
        if not hotkeys_changed or self._hotkeys is None:
            return
        stop = getattr(self._hotkeys, "stop", None)
        if callable(stop):
            stop()
        factory = self._hotkey_factory or _default_hotkey_factory
        listener = factory(
            {
                self._selection_hotkey: self.handle_selection,
                self._ocr_hotkey: self.handle_ocr,
                self._live_hotkey: self.handle_live_ocr,
            }
        )
        start = getattr(listener, "start", None)
        if callable(start):
            start()
        self._hotkeys = listener

    def _run_exclusive(self, job: Callable[[], None]) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            job()
        finally:
            self._busy.release()

    def _selection_job(self) -> None:
        try:
            text = self._read_selected_text()
        except SelectionReadError as exc:
            self._presenter.show(
                TranslateJob(
                    kind=JobKind.SELECTION,
                    status=JobStatus.FAILURE,
                    source_text=None,
                    translated_text=None,
                    error=exc.code,
                )
            )
            return
        if text.strip():
            self._presenter.show_status("translating", source=text)
        result = self._selection.translate_text(
            text,
            self._source_lang,
            self._target_lang,
        )
        self._presenter.show(result)

    def _ocr_job(self) -> None:
        try:
            image_bytes, mime_type = self._capture_region()
        except ImageSourceError as exc:
            if exc.code != "screenshot_cancelled":
                self._presenter.show(
                    TranslateJob(
                        kind=JobKind.OCR,
                        status=JobStatus.FAILURE,
                        source_text=None,
                        translated_text=None,
                        error=exc.code,
                    )
                )
            return
        self._presenter.show_status("translating")
        result = self._ocr_translate.translate_image(
            image_bytes,
            mime_type,
            self._source_lang,
            self._target_lang,
        )
        self._presenter.show(result)


class _MacHotkeyListener:
    def __init__(self, mapping: dict[str, Callable[[], None]]) -> None:
        self._mapping = mapping
        self._impl: object | None = None

    def start(self) -> None:
        try:
            impl = _CarbonHotkeyListener(self._mapping)
            impl.start()
            self._impl = impl
            return
        except Exception as exc:
            print(f"hotkeys: carbon failed ({exc}); using key monitor", file=sys.stderr)
        impl = _PynputHotkeyListener(self._mapping)
        impl.start()
        self._impl = impl

    def stop(self) -> None:
        stop = getattr(self._impl, "stop", None)
        if callable(stop):
            stop()


class _CarbonHotkeyListener:
    def __init__(self, mapping: dict[str, Callable[[], None]]) -> None:
        self._bindings = [
            (parse_hotkey(spec), callback) for spec, callback in mapping.items()
        ]
        if any(spec.mac_vk is None for spec, _ in self._bindings):
            raise RuntimeError("hotkey has no macOS key code")
        self._hotkey_refs: list[object] = []
        self._handler = None
        self._handler_ref = None
        self._by_id: dict[int, Callable[[], None]] = {}
        self._api: object | None = None

    def start(self) -> None:
        from AppKit import NSApplication

        NSApplication.sharedApplication()
        api = _carbon_api()
        self._api = api
        handler = api.Handler(self._on_event)
        self._handler = handler
        spec = api.EventTypeSpec(int.from_bytes(b"keyb", "big"), 5)
        handler_ref = api.c_void_p()
        status = api.InstallEventHandler(
            api.GetApplicationEventTarget(),
            handler,
            1,
            api.byref(spec),
            None,
            api.byref(handler_ref),
        )
        if status != 0:
            raise RuntimeError(f"install hotkey handler failed: {status}")
        self._handler_ref = handler_ref
        target = api.GetApplicationEventTarget()
        signature = int.from_bytes(b"AITL", "big")
        for index, (parsed, callback) in enumerate(self._bindings, start=1):
            assert parsed.mac_vk is not None
            hot_id = api.EventHotKeyID(signature, index)
            ref = api.c_void_p()
            status = api.RegisterEventHotKey(
                parsed.mac_vk,
                _carbon_modifiers(parsed.modifiers),
                hot_id,
                target,
                0,
                api.byref(ref),
            )
            if status != 0:
                self.stop()
                raise RuntimeError(f"register {parsed.key} failed: {status}")
            self._by_id[index] = callback
            self._hotkey_refs.append(ref)

    def stop(self) -> None:
        api = self._api
        if api is None:
            return
        for ref in self._hotkey_refs:
            api.UnregisterEventHotKey(ref)
        self._hotkey_refs.clear()
        if self._handler_ref is not None:
            api.RemoveEventHandler(self._handler_ref)
            self._handler_ref = None
        self._handler = None

    def _on_event(self, _call_ref: object, event: object, _user: object) -> int:
        api = self._api
        if api is None:
            return 0
        ident = api.EventHotKeyID()
        status = api.GetEventParameter(
            event,
            int.from_bytes(b"----", "big"),
            int.from_bytes(b"hkid", "big"),
            None,
            api.sizeof(api.EventHotKeyID),
            None,
            api.byref(ident),
        )
        if status != 0:
            return 0
        callback = self._by_id.get(ident.id)
        if callback is not None:
            threading.Thread(target=_run_hotkey, args=(callback,), daemon=True).start()
        return 0


class _PynputHotkeyListener:
    def __init__(self, mapping: dict[str, Callable[[], None]]) -> None:
        self._matcher = HotkeyMatcher()
        for spec, callback in mapping.items():
            self._matcher.bind(parse_hotkey(spec), callback)
        self._listener = None

    def start(self) -> None:
        from pynput import keyboard

        self._listener = keyboard.Listener(
            on_press=self._matcher.press,
            on_release=self._matcher.release,
        )
        self._listener.start()

    def stop(self) -> None:
        listener = self._listener
        if listener is not None:
            listener.stop()


def _default_hotkey_factory(mapping: dict[str, Callable[[], None]]) -> object:
    if sys.platform == "win32":
        from ai_translate.interfaces.windows_desktop import WindowsHotkeyListener

        return WindowsHotkeyListener(mapping)
    return _MacHotkeyListener(mapping)


def _default_event_loop() -> None:
    if sys.platform != "darwin":
        _sleep_until_interrupt()
        return
    try:
        from AppKit import NSApplication
        from Foundation import NSDate, NSDefaultRunLoopMode, NSRunLoop

        NSApplication.sharedApplication()
    except Exception:
        _sleep_until_interrupt()
        return
    run_loop = NSRunLoop.currentRunLoop()
    while True:
        run_loop.runMode_beforeDate_(
            NSDefaultRunLoopMode,
            NSDate.dateWithTimeIntervalSinceNow_(0.2),
        )


def _sleep_until_interrupt() -> None:
    import time

    while True:
        time.sleep(0.2)


def _accessibility_warning() -> str | None:
    try:
        import HIServices

        trusted = bool(HIServices.AXIsProcessTrusted())
    except Exception:
        return None
    if trusted:
        return None
    host = os.environ.get("AI_TRANSLATE_HOST_NAME", "this terminal or Cursor")
    return (
        "accessibility: not trusted; Option+E translates the clipboard "
        "(copy first). Auto-copy of the current selection needs Accessibility "
        f"for {host}."
    )


def _run_hotkey(callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception as exc:
        print(f"hotkey handler failed: {exc}", file=sys.stderr)


def _carbon_modifiers(modifiers: frozenset[str]) -> int:
    flags = 0
    if "cmd" in modifiers:
        flags |= 1 << 8
    if "shift" in modifiers:
        flags |= 1 << 9
    if "alt" in modifiers:
        flags |= 1 << 11
    if "ctrl" in modifiers:
        flags |= 1 << 12
    return flags


def _carbon_api() -> object:
    import ctypes
    import ctypes.util
    from ctypes import (
        CFUNCTYPE,
        POINTER,
        Structure,
        byref,
        c_int32,
        c_uint32,
        c_void_p,
        sizeof,
    )
    from types import SimpleNamespace

    path = ctypes.util.find_library("Carbon")
    if path is None:
        raise RuntimeError("Carbon framework not found")
    carbon = ctypes.cdll.LoadLibrary(path)

    class EventTypeSpec(Structure):
        _fields_ = [("eventClass", c_uint32), ("eventKind", c_uint32)]

    class EventHotKeyID(Structure):
        _fields_ = [("signature", c_uint32), ("id", c_uint32)]

    handler_type = CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)

    get_target = carbon.GetApplicationEventTarget
    get_target.restype = c_void_p
    get_target.argtypes = []

    install = carbon.InstallEventHandler
    install.restype = c_int32
    install.argtypes = [
        c_void_p,
        handler_type,
        c_uint32,
        POINTER(EventTypeSpec),
        c_void_p,
        POINTER(c_void_p),
    ]

    remove = carbon.RemoveEventHandler
    remove.restype = c_int32
    remove.argtypes = [c_void_p]

    register = carbon.RegisterEventHotKey
    register.restype = c_int32
    register.argtypes = [
        c_uint32,
        c_uint32,
        EventHotKeyID,
        c_void_p,
        c_uint32,
        POINTER(c_void_p),
    ]

    unregister = carbon.UnregisterEventHotKey
    unregister.restype = c_int32
    unregister.argtypes = [c_void_p]

    parameter = carbon.GetEventParameter
    parameter.restype = c_int32
    parameter.argtypes = [
        c_void_p,
        c_uint32,
        c_uint32,
        POINTER(c_uint32),
        c_uint32,
        POINTER(c_uint32),
        c_void_p,
    ]

    return SimpleNamespace(
        Handler=handler_type,
        EventTypeSpec=EventTypeSpec,
        EventHotKeyID=EventHotKeyID,
        GetApplicationEventTarget=get_target,
        InstallEventHandler=install,
        RemoveEventHandler=remove,
        RegisterEventHotKey=register,
        UnregisterEventHotKey=unregister,
        GetEventParameter=parameter,
        c_void_p=c_void_p,
        byref=byref,
        sizeof=sizeof,
    )
