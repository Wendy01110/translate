from __future__ import annotations

import ctypes
import sys
import threading
from collections.abc import Callable, Sequence

from ai_translate.core.hotkeys import parse_hotkey
from ai_translate.core.models import ScreenRect
from ai_translate.interfaces.live_overlay import LIVE_GAP, LIVE_MIN_WIDTH

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
_WINDOWS_LIVE_BAR_HEIGHT = 112.0
_WINDOWS_LIVE_MAX_HEIGHT = 240.0
_REGION_HINT_MARGIN = 18.0
_REGION_HINT_WIDTH = 304.0
_REGION_HINT_HEIGHT = 60.0


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


def windows_region_size_label(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> str:
    return f"{round(abs(end_x - start_x))} × {round(abs(end_y - start_y))} px"


def windows_region_hint_origin(
    virtual_screen: ScreenRect,
    pointer_screen: ScreenRect,
) -> tuple[int, int]:
    virtual = virtual_screen.canonical()
    active = pointer_screen.canonical()
    max_x = max(
        _REGION_HINT_MARGIN,
        virtual.width - _REGION_HINT_WIDTH - _REGION_HINT_MARGIN,
    )
    max_y = max(
        _REGION_HINT_MARGIN,
        virtual.height - _REGION_HINT_HEIGHT - _REGION_HINT_MARGIN,
    )
    return (
        round(
            min(
                max(active.x - virtual.x + _REGION_HINT_MARGIN, _REGION_HINT_MARGIN),
                max_x,
            )
        ),
        round(
            min(
                max(active.y - virtual.y + _REGION_HINT_MARGIN, _REGION_HINT_MARGIN),
                max_y,
            )
        ),
    )


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
                    threading.Thread(
                        target=_run_callback,
                        args=(callback,),
                        daemon=True,
                    ).start()
        finally:
            for ident in registered:
                user32.UnregisterHotKey(None, ident)


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


def windows_monitor_rects(
    enumerator: Callable[[], Sequence[ScreenRect]] | None = None,
) -> tuple[ScreenRect, ...]:
    try:
        values = tuple((enumerator or _enumerate_windows_monitor_rects)())
    except Exception:
        values = ()
    screens = tuple(
        screen.canonical() for screen in values if screen.canonical().is_usable()
    )
    return screens or (windows_virtual_screen_rect(),)


def windows_active_screen_index(
    screens: Sequence[ScreenRect],
    pointer_screen: ScreenRect,
) -> int:
    if not screens:
        raise ValueError("screens must not be empty")
    pointer = pointer_screen.canonical()
    return max(
        range(len(screens)),
        key=lambda index: _screen_overlap_area(screens[index], pointer),
    )


def _enumerate_windows_monitor_rects() -> tuple[ScreenRect, ...]:
    if sys.platform != "win32":
        raise RuntimeError("monitor enumeration requires Windows")
    from ctypes import wintypes

    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HANDLE,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )
    screens: list[ScreenRect] = []

    @callback_type
    def collect(
        _monitor: object,
        _device_context: object,
        rect_pointer: object,
        _data: object,
    ) -> bool:
        rect = rect_pointer.contents
        screens.append(
            ScreenRect(
                x=float(rect.left),
                y=float(rect.top),
                width=float(rect.right - rect.left),
                height=float(rect.bottom - rect.top),
            ).canonical()
        )
        return True

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumDisplayMonitors.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        callback_type,
        wintypes.LPARAM,
    ]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    if not user32.EnumDisplayMonitors(None, None, collect, 0):
        raise OSError(ctypes.get_last_error(), "EnumDisplayMonitors failed")
    return tuple(screens)


def _screen_overlap_area(first: ScreenRect, second: ScreenRect) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    return max(0.0, right - left) * max(0.0, bottom - top)


def windows_pointer_screen_rect() -> ScreenRect:
    if sys.platform != "win32":
        raise RuntimeError("pointer screen metrics require Windows")
    from ctypes import wintypes

    class _MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_MonitorInfo),
    ]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise OSError(ctypes.get_last_error(), "GetCursorPos failed")
    monitor = user32.MonitorFromPoint(point, 2)
    if not monitor:
        raise OSError(ctypes.get_last_error(), "MonitorFromPoint failed")
    info = _MonitorInfo()
    info.cbSize = ctypes.sizeof(_MonitorInfo)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), "GetMonitorInfoW failed")
    work = info.rcWork
    return ScreenRect(
        x=float(work.left),
        y=float(work.top),
        width=float(work.right - work.left),
        height=float(work.bottom - work.top),
    ).canonical()


def windows_live_overlay_rect(
    anchor: ScreenRect,
    *,
    screen: ScreenRect,
    bar_height: float = _WINDOWS_LIVE_BAR_HEIGHT,
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


def windows_live_overlay_height(
    requested_height: float,
    *,
    screen_height: float,
    scale: float = 1.0,
    minimum: float = _WINDOWS_LIVE_BAR_HEIGHT,
    maximum: float = _WINDOWS_LIVE_MAX_HEIGHT,
) -> float:
    normalized_scale = max(0.5, scale)
    scaled_minimum = minimum * normalized_scale
    scaled_maximum = maximum * normalized_scale
    limit = max(1.0, min(scaled_maximum, screen_height))
    return min(max(scaled_minimum, requested_height), limit)


def enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        return


def _run_callback(callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception as exc:
        print(f"Windows desktop action failed: {exc}", file=sys.stderr)
