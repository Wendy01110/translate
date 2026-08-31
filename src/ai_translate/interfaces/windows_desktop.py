from __future__ import annotations

import ctypes
import queue
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ai_translate.core.hotkeys import parse_hotkey
from ai_translate.core.models import ScreenRect, TranslateJob
from ai_translate.interfaces.live_overlay import (
    LIVE_BAR_HEIGHT,
    LIVE_GAP,
    LIVE_MIN_WIDTH,
    format_live_overlay,
    format_live_status,
)
from ai_translate.interfaces.overlay import (
    OverlayContent,
    format_overlay,
    format_status,
    overlay_pin_button_title,
)
from ai_translate.interfaces.region_picker import rect_from_drag

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_MOD_NOREPEAT = 0x4000
_WIN_MODIFIERS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "cmd": 0x0008}
_SPECIAL_VIRTUAL_KEYS = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
}
_UI_POLL_MS = 20
_UI_WAIT_SECONDS = 180.0
_UI_QUEUE_SIZE = 256


def windows_hotkey_codes(spec: str) -> tuple[int, int]:
    parsed = parse_hotkey(spec)
    modifiers = _MOD_NOREPEAT
    for name in parsed.modifiers:
        modifiers |= _WIN_MODIFIERS[name]
    key = parsed.key.lower()
    if len(key) == 1 and "a" <= key <= "z":
        virtual_key = ord(key.upper())
    elif len(key) == 1 and "0" <= key <= "9":
        virtual_key = ord(key)
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        virtual_key = 0x70 + int(key[1:]) - 1
    else:
        virtual_key = _SPECIAL_VIRTUAL_KEYS.get(key, 0)
    if virtual_key == 0:
        raise ValueError(f"Windows 不支持热键按键：{parsed.key}")
    return modifiers, virtual_key


def windows_hotkey_label(spec: str) -> str:
    parsed = parse_hotkey(spec)
    names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Win"}
    order = ("ctrl", "alt", "shift", "cmd")
    parts = [names[name] for name in order if name in parsed.modifiers]
    parts.append(parsed.key.upper())
    return "+".join(parts)


class WindowsHotkeyListener:
    def __init__(self, mapping: dict[str, Callable[[], None]]) -> None:
        self._bindings = [
            (index, spec, windows_hotkey_codes(spec), callback)
            for index, (spec, callback) in enumerate(mapping.items(), start=1)
        ]
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None

    def start(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows hotkeys require Windows")
        if self._thread is not None:
            return
        self._ready.clear()
        self._startup_error = None
        thread = threading.Thread(target=self._run, daemon=True)
        self._thread = thread
        thread.start()
        if not self._ready.wait(5.0):
            self.stop()
            raise RuntimeError("Windows 热键注册超时")
        if self._startup_error is not None:
            error = self._startup_error
            self.stop()
            raise RuntimeError(str(error)) from error

    def stop(self) -> None:
        thread = self._thread
        thread_id = self._thread_id
        if thread is None:
            return
        if thread_id is not None and sys.platform == "win32":
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW(thread_id, _WM_QUIT, 0, 0)
        if thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None
        self._thread_id = None

    def _run(self) -> None:
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        self._thread_id = int(kernel32.GetCurrentThreadId())
        registered: list[int] = []
        callbacks: dict[int, Callable[[], None]] = {}
        try:
            for ident, spec, (modifiers, virtual_key), callback in self._bindings:
                if not user32.RegisterHotKey(None, ident, modifiers, virtual_key):
                    code = ctypes.get_last_error()
                    raise RuntimeError(
                        f"热键 {windows_hotkey_label(spec)} 注册失败（Windows 错误 {code}），请换一个组合"
                    )
                registered.append(ident)
                callbacks[ident] = callback
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            for ident in registered:
                user32.UnregisterHotKey(None, ident)
            return
        self._ready.set()
        message = wintypes.MSG()
        try:
            while True:
                result = int(user32.GetMessageW(ctypes.byref(message), None, 0, 0))
                if result <= 0:
                    break
                if int(message.message) != _WM_HOTKEY:
                    continue
                callback = callbacks.get(int(message.wParam))
                if callback is not None:
                    threading.Thread(target=_run_callback, args=(callback,), daemon=True).start()
        finally:
            for ident in registered:
                user32.UnregisterHotKey(None, ident)


@dataclass
class _UiRequest:
    callback: Callable[[], Any]
    done: threading.Event | None = None
    result: Any = None
    error: BaseException | None = None


class WindowsUiRuntime:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows desktop UI requires Windows")
        enable_windows_dpi_awareness()
        import tkinter as tk

        self._ui_thread = threading.get_ident()
        self._queue: queue.Queue[_UiRequest] = queue.Queue(maxsize=_UI_QUEUE_SIZE)
        self._root = tk.Tk(className="AITranslate")
        self._root.withdraw()
        self._root.title("AI Translate")
        self._closed = False
        self._root.after(_UI_POLL_MS, self._drain)

    @property
    def root(self) -> object:
        return self._root

    def is_ui_thread(self) -> bool:
        return threading.get_ident() == self._ui_thread

    def call_soon(self, callback: Callable[[], Any]) -> None:
        if self._closed:
            return
        if self.is_ui_thread():
            callback()
            return
        try:
            self._queue.put_nowait(_UiRequest(callback=callback))
        except queue.Full:
            print("Windows UI queue is full; action skipped", file=sys.stderr)

    def call_sync(
        self,
        callback: Callable[[], Any],
        *,
        timeout: float = _UI_WAIT_SECONDS,
    ) -> Any:
        if self._closed:
            raise RuntimeError("Windows UI 已关闭")
        if self.is_ui_thread():
            return callback()
        done = threading.Event()
        request = _UiRequest(callback=callback, done=done)
        try:
            self._queue.put_nowait(request)
        except queue.Full as exc:
            raise RuntimeError("Windows UI 队列已满") from exc
        if not done.wait(timeout):
            raise TimeoutError("等待 Windows UI 操作超时")
        if request.error is not None:
            raise request.error
        return request.result

    def run(self) -> None:
        try:
            self._root.mainloop()
        finally:
            self._closed = True
            try:
                self._root.destroy()
            except Exception:
                pass

    def quit(self) -> None:
        self.call_soon(self._root.quit)

    def _drain(self) -> None:
        if self._closed:
            return
        while True:
            try:
                request = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                request.result = request.callback()
            except BaseException as exc:
                request.error = exc
                if request.done is None:
                    print(f"Windows UI action failed: {exc}", file=sys.stderr)
            finally:
                if request.done is not None:
                    request.done.set()
        self._root.after(_UI_POLL_MS, self._drain)


class WindowsRegionPicker:
    needs_main_thread = True

    def __init__(self, runtime: WindowsUiRuntime) -> None:
        self._runtime = runtime
        self._window: object | None = None
        self._on_complete: Callable[[ScreenRect | None], None] | None = None
        self._start: tuple[float, float] | None = None

    def __call__(self) -> ScreenRect | None:
        if self._runtime.is_ui_thread():
            return self._pick_modal()
        done = threading.Event()
        result: list[ScreenRect | None] = []

        def complete(rect: ScreenRect | None) -> None:
            result.append(rect)
            done.set()

        self.start(complete)
        if not done.wait(_UI_WAIT_SECONDS):
            self.cancel()
            return None
        return result[0] if result else None

    def start(self, on_complete: Callable[[ScreenRect | None], None]) -> None:
        self._runtime.call_soon(lambda: self._begin(on_complete))

    def cancel(self) -> None:
        self._runtime.call_soon(lambda: self._finish(None))

    def _pick_modal(self) -> ScreenRect | None:
        import tkinter as tk

        result: list[ScreenRect | None] = []
        completed = tk.BooleanVar(master=self._runtime.root, value=False)

        def finish(rect: ScreenRect | None) -> None:
            result.append(rect)
            completed.set(True)

        self._begin(finish)
        self._runtime.root.wait_variable(completed)
        return result[0] if result else None

    def _begin(self, on_complete: Callable[[ScreenRect | None], None]) -> None:
        if self._window is not None:
            on_complete(None)
            return
        import tkinter as tk

        screen = windows_virtual_screen_rect()
        window = tk.Toplevel(self._runtime.root)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", 0.28)
        geometry = _tk_geometry(screen)
        window.geometry(geometry)
        canvas = tk.Canvas(
            window,
            background="#101820",
            cursor="crosshair",
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)
        instruction = canvas.create_text(
            24,
            24,
            anchor="nw",
            fill="white",
            text="拖拽选择区域，Esc 取消",
            font=("Segoe UI", 14, "bold"),
        )
        del instruction
        state: dict[str, int | None] = {"selection": None}

        def press(event: object) -> None:
            self._start = (float(event.x_root), float(event.y_root))
            if state["selection"] is not None:
                canvas.delete(state["selection"])
            state["selection"] = canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline="#4CC9F0",
                width=3,
                fill="#4361EE",
                stipple="gray50",
            )

        def drag(event: object) -> None:
            if self._start is None or state["selection"] is None:
                return
            start_x, start_y = self._start
            canvas.coords(
                state["selection"],
                start_x - screen.x,
                start_y - screen.y,
                float(event.x_root) - screen.x,
                float(event.y_root) - screen.y,
            )

        def release(event: object) -> None:
            start = self._start
            if start is None:
                self._finish(None)
                return
            rect = rect_from_drag(
                start[0],
                start[1],
                float(event.x_root),
                float(event.y_root),
            )
            self._finish(rect if rect.is_usable() else None)

        canvas.bind("<ButtonPress-1>", press)
        canvas.bind("<B1-Motion>", drag)
        canvas.bind("<ButtonRelease-1>", release)
        window.bind("<Escape>", lambda _event: self._finish(None))
        self._window = window
        self._on_complete = on_complete
        window.deiconify()
        window.lift()
        window.focus_force()

    def _finish(self, rect: ScreenRect | None) -> None:
        window = self._window
        callback = self._on_complete
        self._window = None
        self._on_complete = None
        self._start = None
        if window is not None:
            window.destroy()
        if callback is not None:
            self._runtime.root.after(40, lambda: callback(rect))


class WindowsOverlayPresenter:
    def __init__(self, runtime: WindowsUiRuntime) -> None:
        self._runtime = runtime
        self._window: object | None = None
        self._title: object | None = None
        self._source: object | None = None
        self._translation: object | None = None
        self._footnote: object | None = None
        self._pin_button: object | None = None
        self._pinned = False

    def show_status(self, message: str, source: str | None = None) -> None:
        content = format_status(message, source=source or "")
        self._runtime.call_soon(lambda: self._show(content))

    def show(self, job: TranslateJob) -> None:
        content = format_overlay(job)
        self._runtime.call_soon(lambda: self._show(content))

    def _show(self, content: OverlayContent) -> None:
        created = self._window is None
        if created:
            self._create()
        assert self._window is not None
        self._window.title(content.title)
        self._title.configure(text=content.title)
        _replace_text(self._source, content.source)
        _replace_text(self._translation, content.translation)
        self._footnote.configure(text=content.footnote)
        self._window.deiconify()
        _set_windows_overlay_pinned(self._window, pinned=True)
        self._window.lift()
        if not self._pinned:
            self._runtime.root.after_idle(self._restore_pin_state)
        if created:
            _center_window(self._window)
            self._window.focus_force()

    def _toggle_pin(self) -> None:
        self._pinned = not self._pinned
        self._restore_pin_state()
        if self._window is not None:
            self._window.lift()

    def _restore_pin_state(self) -> None:
        if self._window is None or self._pin_button is None:
            return
        _set_windows_overlay_pinned(self._window, pinned=self._pinned)
        self._pin_button.configure(
            text=overlay_pin_button_title(pinned=self._pinned)
        )

    def _create(self) -> None:
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText

        window = tk.Toplevel(self._runtime.root)
        window.withdraw()
        window.title("AI Translate")
        window.geometry("560x430")
        window.minsize(420, 320)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        window.columnconfigure(0, weight=1)
        window.columnconfigure(1, weight=0)
        window.rowconfigure(1, weight=1)
        window.rowconfigure(3, weight=1)
        title = tk.Label(window, anchor="w", font=("Segoe UI", 13, "bold"))
        title.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        pin_button = ttk.Button(
            window,
            text=overlay_pin_button_title(pinned=self._pinned),
            command=self._toggle_pin,
            width=8,
        )
        pin_button.grid(row=0, column=1, sticky="e", padx=(0, 14), pady=(10, 2))
        source = ScrolledText(window, wrap="word", height=6, font=("Segoe UI", 11))
        source.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=14,
            pady=4,
        )
        translation_label = tk.Label(window, text="译文", anchor="w")
        translation_label.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=14,
            pady=(8, 0),
        )
        translation = ScrolledText(window, wrap="word", height=7, font=("Segoe UI", 12))
        translation.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=14,
            pady=4,
        )
        footnote = tk.Label(window, anchor="w", foreground="#666666")
        footnote.grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=14,
            pady=(2, 10),
        )
        self._window = window
        self._title = title
        self._source = source
        self._translation = translation
        self._footnote = footnote
        self._pin_button = pin_button
        self._restore_pin_state()


def _set_windows_overlay_pinned(window: object, *, pinned: bool) -> None:
    window.attributes("-topmost", pinned)


class WindowsLiveOverlayPresenter:
    def __init__(
        self,
        runtime: WindowsUiRuntime,
        *,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        self._runtime = runtime
        self._on_stop = on_stop
        self._anchor: ScreenRect | None = None
        self._window: object | None = None
        self._title: object | None = None
        self._source: object | None = None
        self._translation: object | None = None

    def set_stop(self, on_stop: Callable[[], None] | None) -> None:
        self._on_stop = on_stop

    def set_anchor(self, rect: ScreenRect | None) -> None:
        self._anchor = rect
        self._runtime.call_soon(self._position)

    def show_status(self, message: str, source: str | None = None) -> None:
        del source
        content = format_live_status(message)
        self._runtime.call_soon(lambda: self._show(content))

    def show(self, job: TranslateJob) -> None:
        content = format_live_overlay(job)
        self._runtime.call_soon(lambda: self._show(content))

    def hide(self) -> None:
        self._runtime.call_soon(self._hide)

    def _show(self, content: OverlayContent) -> None:
        if self._window is None:
            self._create()
        self._title.configure(text=content.title)
        self._source.configure(text=content.source)
        self._translation.configure(text=content.translation)
        self._position()
        self._window.deiconify()
        self._window.lift()
        _make_window_no_activate(self._window)

    def _create(self) -> None:
        import tkinter as tk

        window = tk.Toplevel(self._runtime.root)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(background="#111827")
        window.columnconfigure(0, weight=1)
        title = tk.Label(
            window,
            anchor="w",
            background="#111827",
            foreground="#93C5FD",
            font=("Segoe UI", 9, "bold"),
        )
        title.grid(row=0, column=0, sticky="ew", padx=(10, 4), pady=(6, 0))
        close = tk.Button(
            window,
            text="×",
            command=self._stop,
            relief="flat",
            borderwidth=0,
            background="#111827",
            foreground="white",
            activebackground="#374151",
            activeforeground="white",
        )
        close.grid(row=0, column=1, sticky="ne", padx=(0, 5), pady=(2, 0))
        source = tk.Label(
            window,
            anchor="w",
            justify="left",
            background="#111827",
            foreground="#9CA3AF",
            font=("Segoe UI", 9),
        )
        source.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
        translation = tk.Label(
            window,
            anchor="w",
            justify="left",
            background="#111827",
            foreground="white",
            font=("Segoe UI", 12),
        )
        translation.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 7))
        self._window = window
        self._title = title
        self._source = source
        self._translation = translation

    def _position(self) -> None:
        window = self._window
        anchor = self._anchor
        if window is None or anchor is None:
            return
        screen = windows_virtual_screen_rect()
        rect = windows_live_overlay_rect(anchor, screen=screen)
        self._source.configure(wraplength=max(240, int(rect.width) - 20))
        self._translation.configure(wraplength=max(240, int(rect.width) - 20))
        window.geometry(_tk_geometry(rect))

    def _hide(self) -> None:
        if self._window is not None:
            self._window.withdraw()

    def _stop(self) -> None:
        self._hide()
        callback = self._on_stop
        if callback is not None:
            threading.Thread(target=callback, daemon=True).start()


class WindowsTray:
    def __init__(
        self,
        *,
        listener: object,
        open_settings: Callable[[], None] | None,
        open_input: Callable[[], None] | None,
        quit_app: Callable[[], None],
    ) -> None:
        self._listener = listener
        self._open_settings = open_settings
        self._open_input = open_input
        self._quit_app = quit_app
        self._icon: object | None = None

    def start(self) -> None:
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem(
                lambda _item: f"划词翻译  {windows_hotkey_label(self._listener.selection_hotkey)}",
                lambda _icon, _item: _start_callback(self._listener.handle_selection),
            ),
            pystray.MenuItem(
                lambda _item: f"截图翻译  {windows_hotkey_label(self._listener.ocr_hotkey)}",
                lambda _icon, _item: _start_callback(self._listener.handle_ocr),
            ),
            pystray.MenuItem(
                lambda _item: (
                    "停止实时翻译"
                    if self._listener.live_running
                    else f"实时翻译  {windows_hotkey_label(self._listener.live_hotkey)}"
                ),
                lambda _icon, _item: _start_callback(self._listener.handle_live_ocr),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "输入翻译…",
                lambda _icon, _item: self._invoke_ui(self._open_input),
            ),
            pystray.MenuItem(
                "设置…",
                lambda _icon, _item: self._invoke_ui(self._open_settings),
            ),
            pystray.MenuItem("退出", lambda _icon, _item: self._quit_app()),
        )
        icon = pystray.Icon("AI Translate", _tray_image(), "AI Translate", menu)
        self._icon = icon
        icon.run_detached()

    def stop(self) -> None:
        icon = self._icon
        self._icon = None
        if icon is not None:
            icon.stop()

    @staticmethod
    def _invoke_ui(callback: Callable[[], None] | None) -> None:
        if callback is not None:
            callback()


def run_windows_status_app(
    listener: object,
    *,
    runtime: WindowsUiRuntime,
    acquire_instance: Callable[[], bool],
    release_instance: Callable[[], None],
    open_settings: Callable[[], None] | None = None,
    open_input: Callable[[], None] | None = None,
) -> int:
    if sys.platform != "win32":
        print("app is only supported on macOS and Windows", file=sys.stderr)
        return 2
    if not acquire_instance():
        print("AI Translate is already running", file=sys.stderr)
        return 1
    tray: WindowsTray | None = None

    def quit_app() -> None:
        listener.stop_live()
        runtime.quit()

    try:
        tray = WindowsTray(
            listener=listener,
            open_settings=open_settings,
            open_input=open_input,
            quit_app=quit_app,
        )
        tray.start()
        try:
            return listener.run()
        except Exception as exc:
            print(f"Windows app failed: {exc}", file=sys.stderr)
            from tkinter import messagebox

            messagebox.showerror("AI Translate", str(exc), parent=runtime.root)
            return 2
    finally:
        if tray is not None:
            tray.stop()
        release_instance()


def windows_virtual_screen_rect(
    metrics: Callable[[int], int] | None = None,
) -> ScreenRect:
    if metrics is None:
        if sys.platform != "win32":
            raise RuntimeError("virtual screen metrics require Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        metrics = user32.GetSystemMetrics
    return ScreenRect(
        x=float(metrics(76)),
        y=float(metrics(77)),
        width=float(metrics(78)),
        height=float(metrics(79)),
    ).canonical()


def windows_live_overlay_rect(
    anchor: ScreenRect,
    *,
    screen: ScreenRect,
    bar_height: float = LIVE_BAR_HEIGHT,
    gap: float = LIVE_GAP,
    min_width: float = LIVE_MIN_WIDTH,
) -> ScreenRect:
    region = anchor.canonical()
    display = screen.canonical()
    width = min(max(region.width, min_width), display.width)
    x = min(max(region.x, display.x), display.x + display.width - width)
    below_y = region.y + region.height + gap
    above_y = region.y - gap - bar_height
    if below_y + bar_height <= display.y + display.height:
        y = below_y
    elif above_y >= display.y:
        y = above_y
    else:
        y = min(
            max(below_y, display.y),
            display.y + display.height - bar_height,
        )
    return ScreenRect(x=x, y=y, width=width, height=bar_height)


def enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        return


def _make_window_no_activate(window: object) -> None:
    if sys.platform != "win32":
        return
    try:
        from ctypes import wintypes

        window.update_idletasks()
        hwnd = int(window.winfo_id())
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_window_long = user32.GetWindowLongW
        set_window_long = user32.SetWindowLongW
        get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        get_window_long.restype = ctypes.c_long
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        set_window_long.restype = ctypes.c_long
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        style = int(get_window_long(hwnd, -20))
        set_window_long(hwnd, -20, style | 0x08000000 | 0x00000080)
        user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0013)
    except Exception:
        return


def _replace_text(widget: object, value: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")


def _center_window(window: object) -> None:
    window.update_idletasks()
    width = int(window.winfo_width())
    height = int(window.winfo_height())
    screen = windows_virtual_screen_rect()
    x = int(screen.x + (screen.width - width) / 2)
    y = int(screen.y + (screen.height - height) / 2)
    window.geometry(f"{x:+d}{y:+d}")


def _tk_geometry(rect: ScreenRect) -> str:
    canonical = rect.canonical()
    return (
        f"{max(1, round(canonical.width))}x{max(1, round(canonical.height))}"
        f"{round(canonical.x):+d}{round(canonical.y):+d}"
    )


def _tray_image() -> object:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), "#2563EB")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=13, fill="#2563EB")
    draw.line((18, 20, 46, 20), fill="white", width=5)
    draw.line((18, 32, 40, 32), fill="white", width=5)
    draw.line((18, 44, 34, 44), fill="white", width=5)
    return image


def _run_callback(callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception as exc:
        print(f"Windows desktop action failed: {exc}", file=sys.stderr)


def _start_callback(callback: Callable[[], None]) -> None:
    threading.Thread(target=_run_callback, args=(callback,), daemon=True).start()
