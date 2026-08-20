from __future__ import annotations

import ctypes
import io
import math
import sys
import time
from collections.abc import Callable

from ai_translate.core.errors import ImageSourceError, SelectionReadError
from ai_translate.core.models import ScreenRect
from ai_translate.infrastructure.image_file import MAX_IMAGE_BYTES

_CLIPBOARD_RETRIES = 10
_CLIPBOARD_RETRY_SECONDS = 0.02
_MODIFIER_WAIT_SECONDS = 0.8
_ERROR_ALREADY_EXISTS = 183
MAX_CAPTURE_PIXELS = 40_000_000


class WindowsClipboard:
    def __init__(
        self,
        *,
        api_factory: Callable[[], object] | None = None,
        wait: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_factory = api_factory or _clipboard_api
        self._wait = wait

    def read(self) -> str:
        api = self._api_factory()
        self._open(api, error="clipboard_read_failed")
        try:
            unicode_format = int(getattr(api, "CF_UNICODETEXT"))
            if not bool(api.IsClipboardFormatAvailable(unicode_format)):
                return ""
            value = api.GetClipboardData(unicode_format)
            return value if isinstance(value, str) else str(value or "")
        except SelectionReadError:
            raise
        except Exception as exc:
            raise SelectionReadError("clipboard_read_failed") from exc
        finally:
            api.CloseClipboard()

    def write(self, text: str) -> None:
        api = self._api_factory()
        self._open(api, error="clipboard_write_failed")
        try:
            unicode_format = int(getattr(api, "CF_UNICODETEXT"))
            api.EmptyClipboard()
            api.SetClipboardText(text, unicode_format)
        except SelectionReadError:
            raise
        except Exception as exc:
            raise SelectionReadError("clipboard_write_failed") from exc
        finally:
            api.CloseClipboard()

    def _open(self, api: object, *, error: str) -> None:
        for attempt in range(_CLIPBOARD_RETRIES):
            try:
                api.OpenClipboard()
                return
            except Exception as exc:
                if attempt + 1 == _CLIPBOARD_RETRIES:
                    raise SelectionReadError(error) from exc
                self._wait(_CLIPBOARD_RETRY_SECONDS)


class WindowsRectCapture:
    def __init__(
        self,
        *,
        grabber: Callable[[ScreenRect], bytes] | None = None,
    ) -> None:
        self._grabber = grabber or _grab_rect_png

    def capture_rect(self, rect: ScreenRect) -> tuple[bytes, str]:
        canonical = rect.canonical()
        if not canonical.is_usable():
            raise ImageSourceError("region_too_small")
        if canonical.width * canonical.height > MAX_CAPTURE_PIXELS:
            raise ImageSourceError("image_too_large")
        data = self._grabber(canonical)
        if not data:
            raise ImageSourceError("screenshot_failed")
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageSourceError("image_too_large")
        return data, "image/png"


class WindowsRegionScreenshot:
    def __init__(
        self,
        *,
        pick_region: Callable[[], ScreenRect | None],
        capture_rect: Callable[[ScreenRect], tuple[bytes, str]],
    ) -> None:
        self._pick_region = pick_region
        self._capture_rect = capture_rect

    def capture_region(self) -> tuple[bytes, str]:
        rect = self._pick_region()
        if rect is None:
            raise ImageSourceError("screenshot_cancelled")
        return self._capture_rect(rect)


class WindowsInstanceLock:
    def __init__(self, name: str = "Local\\AITranslateDesktop") -> None:
        self._name = name
        self._handle: int | None = None

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return False
        if self._handle is not None:
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            raise OSError(ctypes.get_last_error(), "cannot create instance mutex")
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return False
        self._handle = int(handle)
        return True

    def close(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def send_windows_copy_key() -> None:
    if sys.platform != "win32":
        raise SelectionReadError("copy_simulation_failed")
    _wait_windows_modifiers_released()
    from ctypes import wintypes

    ulong_ptr = ctypes.c_size_t

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class KeyboardInput(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class HardwareInput(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class InputUnion(ctypes.Union):
        _fields_ = [
            ("mi", MouseInput),
            ("ki", KeyboardInput),
            ("hi", HardwareInput),
        ]

    class Input(ctypes.Structure):
        _anonymous_ = ("value",)
        _fields_ = [("type", wintypes.DWORD), ("value", InputUnion)]

    input_keyboard = 1
    key_up = 0x0002
    vk_control = 0x11
    vk_c = 0x43
    events = (Input * 4)()
    for index, (key, flags) in enumerate(
        ((vk_control, 0), (vk_c, 0), (vk_c, key_up), (vk_control, key_up))
    ):
        events[index].type = input_keyboard
        events[index].ki = KeyboardInput(key, 0, flags, 0, 0)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    sent = int(user32.SendInput(len(events), events, ctypes.sizeof(Input)))
    if sent != len(events):
        raise SelectionReadError("copy_simulation_failed")


def _wait_windows_modifiers_released(
    *, timeout: float = _MODIFIER_WAIT_SECONDS
) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    pressed = 0x8000
    modifiers = (0x10, 0x11, 0x12, 0x5B, 0x5C)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all((int(user32.GetAsyncKeyState(key)) & pressed) == 0 for key in modifiers):
            return
        time.sleep(0.03)


def _grab_rect_png(rect: ScreenRect) -> bytes:
    from PIL import ImageGrab

    canonical = rect.canonical()
    left = math.floor(canonical.x)
    top = math.floor(canonical.y)
    right = math.ceil(canonical.x + canonical.width)
    bottom = math.ceil(canonical.y + canonical.height)
    image = ImageGrab.grab(
        bbox=(left, top, right, bottom),
        include_layered_windows=False,
        all_screens=True,
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _clipboard_api() -> object:
    if sys.platform != "win32":
        raise SelectionReadError("clipboard_read_failed")
    import win32clipboard
    import win32con

    setattr(win32clipboard, "CF_UNICODETEXT", win32con.CF_UNICODETEXT)
    return win32clipboard
