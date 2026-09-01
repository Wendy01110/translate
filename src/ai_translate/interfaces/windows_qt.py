from __future__ import annotations

import ctypes
import queue
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_translate.config import AppPreferences
from ai_translate.core.models import JobKind, JobStatus, ScreenRect, TranslateJob
from ai_translate.interfaces.live_overlay import format_live_overlay, format_live_status
from ai_translate.interfaces.overlay import (
    OVERLAY_TRANSLATING_BUTTON_TITLE,
    OverlayContent,
    format_status,
    format_translation_workspace,
    normalize_target_language_options,
)
from ai_translate.interfaces.region_picker import rect_from_drag
from ai_translate.interfaces.settings import (
    IMAGE_MODE_OPTIONS,
    LOCAL_ADVANCED_MODEL_TIER_OPTIONS,
    PROVIDER_OPTIONS,
    SOURCE_LANG_OPTIONS,
    TARGET_LANG_OPTIONS,
    parse_settings_form,
)
from ai_translate.interfaces.windows_desktop import (
    enable_windows_dpi_awareness,
    windows_active_screen_index,
    windows_hotkey_label,
    windows_live_overlay_height,
    windows_live_overlay_rect,
    windows_monitor_rects,
    windows_pointer_screen_rect,
    windows_region_hint_origin,
    windows_region_size_label,
    windows_virtual_screen_rect,
)

_UI_QUEUE_SIZE = 128
_UI_POLL_MS = 16
_UI_WAIT_SECONDS = 90.0
_QML_DIRECTORY = Path(__file__).with_name("qml")
_APP_ICON = _QML_DIRECTORY / "icons" / "app.svg"

_WINDOWS_ENGINE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("auto", "自动（本地高级 → API 两层）"),
    ("paddle", "只本地高级（PaddleOCR）"),
    ("standard", "只 API 普通（OCR.space）"),
    ("model", "只 API 高级模型"),
)


@dataclass
class _UiRequest:
    callback: Callable[[], Any]
    done: threading.Event | None = None
    result: Any = None
    error: BaseException | None = None


class WindowsUiRuntime:
    """One QApplication, one QML engine, and a bounded cross-thread UI queue."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows desktop UI requires Windows")
        enable_windows_dpi_awareness()

        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QIcon
        from PySide6.QtQml import QQmlEngine
        from PySide6.QtQuickControls2 import QQuickStyle
        from PySide6.QtWidgets import QApplication

        QQuickStyle.setStyle("FluentWinUI3")
        QQuickStyle.setFallbackStyle("Basic")
        app = QApplication.instance()
        if app is None:
            app = QApplication([sys.argv[0] if sys.argv else "ai-translate"])
        if not isinstance(app, QApplication):
            raise RuntimeError("AI Translate requires a QApplication")
        app.setApplicationName("AI Translate")
        app.setOrganizationName("AI Translate")
        app.setQuitOnLastWindowClosed(False)
        app.setWindowIcon(QIcon(str(_APP_ICON)))

        self._app = app
        self._engine = QQmlEngine()
        self._engine.addImportPath(str(_QML_DIRECTORY))
        self._ui_thread = threading.get_ident()
        self._queue: queue.Queue[_UiRequest] = queue.Queue(maxsize=_UI_QUEUE_SIZE)
        self._closed = False
        self._windows: list[object] = []
        self._components: dict[int, object] = {}
        self._timer = QTimer()
        self._timer.setInterval(_UI_POLL_MS)
        self._timer.timeout.connect(self._drain)
        self._timer.start()

    @property
    def app(self) -> object:
        return self._app

    @property
    def root(self) -> object:
        """Compatibility alias for code that only needs the application owner."""

        return self._app

    @property
    def dpi_scale(self) -> float:
        screen = self._app.primaryScreen()
        if screen is None:
            return 1.0
        return max(1.0, float(screen.logicalDotsPerInch()) / 96.0)

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

    def call_later(self, milliseconds: int, callback: Callable[[], Any]) -> None:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(max(0, milliseconds), callback)

    def create_window(
        self,
        qml_name: str,
        initial_properties: dict[str, object] | None = None,
    ) -> object:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent, QQmlEngine

        path = _QML_DIRECTORY / qml_name
        component = QQmlComponent(self._engine, QUrl.fromLocalFile(str(path)))
        if component.isError():
            details = "\n".join(error.toString() for error in component.errors())
            raise RuntimeError(f"无法加载 {qml_name}：\n{details}")
        window = component.createWithInitialProperties(initial_properties or {})
        if window is None:
            details = "\n".join(error.toString() for error in component.errors())
            raise RuntimeError(f"无法创建 {qml_name}：\n{details}")
        QQmlEngine.setObjectOwnership(window, QQmlEngine.ObjectOwnership.CppOwnership)
        self._windows.append(window)
        self._components[id(window)] = component
        return window

    def destroy_window(self, window: object) -> None:
        if window in self._windows:
            self._windows.remove(window)
        self._components.pop(id(window), None)
        try:
            from shiboken6 import isValid

            if not isValid(window):
                return
        except ImportError:
            pass
        close = getattr(window, "close", None)
        if callable(close):
            try:
                close()
            except RuntimeError:
                return
        delete_later = getattr(window, "deleteLater", None)
        if callable(delete_later):
            try:
                delete_later()
            except RuntimeError:
                pass

    def connect_signal(
        self,
        window: object,
        signature: str,
        callback: Callable[..., Any],
    ) -> None:
        from PySide6.QtCore import QObject, SIGNAL

        QObject.connect(window, SIGNAL(signature), callback)

    def present_window(
        self,
        window: object,
        *,
        focus_source: bool | None = None,
    ) -> None:
        from PySide6.QtCore import Q_ARG, QMetaObject

        if focus_source is None:
            QMetaObject.invokeMethod(window, "present")
        else:
            QMetaObject.invokeMethod(
                window,
                "present",
                Q_ARG("QVariant", focus_source),
            )
        window.show()
        window.raise_()
        if focus_source is True:
            window.requestActivate()

    def hide_window(self, window: object) -> None:
        window.hide()

    def center_window(self, window: object) -> None:
        from PySide6.QtGui import QCursor

        screen = self._app.screenAt(QCursor.pos()) or self._app.primaryScreen()
        if screen is None:
            return
        bounds = screen.availableGeometry()
        x = bounds.x() + max(0, (bounds.width() - int(window.width())) // 2)
        y = bounds.y() + max(0, (bounds.height() - int(window.height())) // 2)
        window.setPosition(x, y)

    def process_events(self) -> None:
        self._app.processEvents()

    def device_pixel_ratio(self, window: object) -> float:
        try:
            return max(1.0, float(window.devicePixelRatio()))
        except Exception:
            return 1.0

    def set_topmost(self, window: object, *, topmost: bool) -> None:
        _set_qt_window_topmost(window, topmost=topmost)

    def set_no_activate(self, window: object) -> None:
        _set_qt_window_no_activate(window)

    def set_native_rect(self, window: object, rect: ScreenRect) -> None:
        _set_qt_window_rect(window, rect)

    def set_clipboard_text(self, text: str) -> None:
        self._app.clipboard().setText(text)

    def show_error(self, title: str, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(None, title, message)

    def run(self) -> None:
        try:
            self._app.exec()
        finally:
            self._closed = True
            self._timer.stop()

    def quit(self) -> None:
        self.call_soon(self._app.quit)

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


class WindowsOverlayPresenter:
    def __init__(self, runtime: WindowsUiRuntime) -> None:
        self._runtime = runtime
        self._window: object | None = None
        self._translate: Callable[[str], TranslateJob] | None = None
        self._target_language_options: tuple[tuple[str, str], ...] = ()
        self._target_language = ""
        self._target_language_changed: Callable[[str], None] | None = None
        self._source_editable = False
        self._busy = False
        self._pinned = False
        self._copy_feedback_generation = 0

    def show_status(self, message: str, source: str | None = None) -> None:
        display_message = (
            OVERLAY_TRANSLATING_BUTTON_TITLE if message == "translating" else message
        )
        content = format_status(display_message, source=source or "")
        self._runtime.call_soon(lambda: self._show(content, busy=True))

    def show(self, job: TranslateJob) -> None:
        self._runtime.call_soon(
            lambda: self._show(format_translation_workspace(job), busy=False)
        )

    def show_input(self) -> None:
        self._runtime.call_soon(self._show_input_ui)

    def set_translate(self, translate: Callable[[str], TranslateJob]) -> None:
        self._translate = translate
        self._runtime.call_soon(self._sync_state)

    def configure_target_languages(
        self,
        options: tuple[tuple[str, str], ...],
        *,
        current: str,
        on_change: Callable[[str], None],
    ) -> None:
        normalized = normalize_target_language_options(options, current)
        self._target_language_options = normalized
        self._target_language = current.strip().lower() or normalized[0][0]
        self._target_language_changed = on_change
        self._runtime.call_soon(self._sync_state)

    def set_target_language(self, target_language: str) -> None:
        selected = target_language.strip().lower()
        if not selected:
            return

        def apply() -> None:
            self._target_language_options = normalize_target_language_options(
                self._target_language_options,
                selected,
            )
            self._target_language = selected
            self._sync_state()

        self._runtime.call_soon(apply)

    def _create(self) -> None:
        window = self._runtime.create_window("Workspace.qml")
        self._runtime.connect_signal(
            window,
            "translateRequested(QString)",
            self._request_translate,
        )
        self._runtime.connect_signal(
            window,
            "targetLanguageSelected(int)",
            self._target_language_selected,
        )
        self._runtime.connect_signal(window, "pinRequested()", self._toggle_pin)
        self._runtime.connect_signal(window, "copyRequested()", self._copy_translation)
        self._window = window
        self._sync_state()

    def _show_input_ui(self) -> None:
        if self._busy and self._window is not None:
            self._runtime.present_window(self._window, focus_source=False)
            return
        self._show(format_translation_workspace(), focus_source=True, busy=False)

    def _show(
        self,
        content: OverlayContent,
        *,
        focus_source: bool = False,
        busy: bool | None = None,
    ) -> None:
        created = self._window is None
        if created:
            self._create()
        assert self._window is not None
        if busy is not None:
            self._busy = busy
        self._source_editable = content.source_editable
        self._window.setProperty("sourceText", content.source)
        self._window.setProperty("translationText", content.translation)
        self._window.setProperty("footnote", content.footnote)
        self._reset_copy_feedback()
        self._sync_state()
        if created:
            self._runtime.center_window(self._window)
        self._runtime.present_window(self._window, focus_source=created or focus_source)
        if self._pinned:
            self._runtime.set_topmost(self._window, topmost=True)
        else:
            self._runtime.set_topmost(self._window, topmost=True)
            self._runtime.call_later(35, self._restore_pin_state)

    def _request_translate(self, text: object = "") -> None:
        translate = self._translate
        if self._busy or not self._source_editable or translate is None:
            return
        source = str(text)
        if not source and self._window is not None:
            source = str(self._window.property("sourceText") or "")
        self._busy = True
        assert self._window is not None
        self._window.setProperty("footnote", OVERLAY_TRANSLATING_BUTTON_TITLE)
        self._window.setProperty("translationText", "")
        self._sync_state()

        def run() -> None:
            try:
                job = translate(source)
            except Exception as exc:
                job = TranslateJob(
                    kind=JobKind.SELECTION,
                    status=JobStatus.FAILURE,
                    source_text=source,
                    translated_text=None,
                    error=str(exc),
                )
            self._runtime.call_soon(lambda: self._show_typed_translation(job))

        threading.Thread(target=run, daemon=True).start()

    def _show_typed_translation(self, job: TranslateJob) -> None:
        assert self._window is not None
        self._busy = False
        content = format_translation_workspace(job)
        self._source_editable = True
        self._window.setProperty("sourceText", content.source)
        self._window.setProperty(
            "translationText",
            "请输入要翻译的文字。" if job.error == "empty_text" else content.translation,
        )
        self._window.setProperty("footnote", content.footnote)
        self._reset_copy_feedback()
        self._sync_state()

    def _target_language_selected(self, index: int) -> None:
        if self._busy or not 0 <= int(index) < len(self._target_language_options):
            return
        selected = self._target_language_options[int(index)][0]
        if selected == self._target_language:
            return
        self._target_language = selected
        callback = self._target_language_changed
        if callback is not None:
            callback(selected)

    def _copy_translation(self) -> None:
        if self._window is None:
            return
        text = str(self._window.property("translationText") or "")
        if not text:
            return
        self._runtime.set_clipboard_text(text)
        self._copy_feedback_generation += 1
        generation = self._copy_feedback_generation
        self._window.setProperty("copyFeedback", True)
        self._runtime.call_later(
            1200,
            lambda: self._restore_copy_feedback(generation),
        )

    def _restore_copy_feedback(self, generation: int) -> None:
        if generation != self._copy_feedback_generation or self._window is None:
            return
        self._window.setProperty("copyFeedback", False)

    def _reset_copy_feedback(self) -> None:
        self._copy_feedback_generation += 1
        if self._window is not None:
            self._window.setProperty("copyFeedback", False)

    def _toggle_pin(self) -> None:
        self._pinned = not self._pinned
        self._restore_pin_state()
        if self._window is not None:
            self._runtime.present_window(self._window)

    def _restore_pin_state(self) -> None:
        if self._window is None:
            return
        self._window.setProperty("pinned", self._pinned)
        self._runtime.set_topmost(self._window, topmost=self._pinned)

    def _sync_state(self) -> None:
        if self._window is None:
            return
        labels = [label for _code, label in self._target_language_options]
        selected_index = next(
            (
                index
                for index, (code, _label) in enumerate(self._target_language_options)
                if code == self._target_language
            ),
            0,
        )
        self._window.setProperty("targetLabels", labels)
        self._window.setProperty("targetIndex", selected_index)
        self._window.setProperty("sourceEditable", self._source_editable)
        self._window.setProperty("busy", self._busy)
        self._window.setProperty("pinned", self._pinned)
        self._window.setProperty("translateAvailable", self._translate is not None)


@dataclass
class _PickerSurface:
    window: object
    screen: ScreenRect
    scale: float = 1.0


class WindowsRegionPicker:
    needs_main_thread = True

    def __init__(self, runtime: WindowsUiRuntime) -> None:
        self._runtime = runtime
        self._surfaces: list[_PickerSurface] = []
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
        from PySide6.QtCore import QEventLoop

        loop = QEventLoop()
        result: list[ScreenRect | None] = []

        def complete(rect: ScreenRect | None) -> None:
            result.append(rect)
            loop.quit()

        self._begin(complete)
        loop.exec()
        return result[0] if result else None

    def _begin(self, on_complete: Callable[[ScreenRect | None], None]) -> None:
        if self._on_complete is not None:
            on_complete(None)
            return
        virtual_screen = windows_virtual_screen_rect()
        screens = windows_monitor_rects()
        try:
            pointer_screen = windows_pointer_screen_rect()
        except Exception:
            pointer_screen = virtual_screen
        active_index = windows_active_screen_index(screens, pointer_screen)
        hint_x, hint_y = windows_region_hint_origin(virtual_screen, pointer_screen)
        hint_global_x = virtual_screen.x + hint_x
        hint_global_y = virtual_screen.y + hint_y

        self._surfaces = []
        self._on_complete = on_complete
        try:
            for index, screen in enumerate(screens):
                window = self._runtime.create_window(
                    "RegionOverlay.qml",
                    {
                        "activeSurface": index == active_index,
                        "showHint": index == active_index,
                        "width": max(1, round(screen.width)),
                        "height": max(1, round(screen.height)),
                    },
                )
                surface = _PickerSurface(window=window, screen=screen)
                self._surfaces.append(surface)
                self._runtime.connect_signal(
                    window,
                    "pressedAt(double,double)",
                    lambda x, y, item=surface: self._press(
                        item,
                        float(x),
                        float(y),
                    ),
                )
                self._runtime.connect_signal(
                    window,
                    "movedAt(double,double)",
                    lambda x, y, item=surface: self._drag(
                        item,
                        float(x),
                        float(y),
                    ),
                )
                self._runtime.connect_signal(
                    window,
                    "releasedAt(double,double)",
                    lambda x, y, item=surface: self._release(
                        item,
                        float(x),
                        float(y),
                    ),
                )
                self._runtime.connect_signal(
                    window,
                    "cancelRequested()",
                    lambda: self._finish(None),
                )
                self._runtime.set_native_rect(window, screen)
                self._runtime.present_window(window)
                self._runtime.process_events()
                if self._on_complete is not on_complete:
                    return
                surface.scale = self._runtime.device_pixel_ratio(window)
                if index == active_index:
                    window.setProperty(
                        "hintX",
                        max(12.0, (hint_global_x - screen.x) / surface.scale),
                    )
                    window.setProperty(
                        "hintY",
                        max(12.0, (hint_global_y - screen.y) / surface.scale),
                    )
        except Exception:
            if self._on_complete is on_complete:
                self._finish(None)
            raise

    def _global_point(
        self,
        surface: _PickerSurface,
        x: float,
        y: float,
    ) -> tuple[float, float]:
        scale = self._runtime.device_pixel_ratio(surface.window)
        surface.scale = scale
        return surface.screen.x + x * scale, surface.screen.y + y * scale

    def _press(self, surface: _PickerSurface, x: float, y: float) -> None:
        self._start = self._global_point(surface, x, y)
        self._update_drag(*self._start)

    def _drag(self, surface: _PickerSurface, x: float, y: float) -> None:
        self._update_drag(*self._global_point(surface, x, y))

    def _release(self, surface: _PickerSurface, x: float, y: float) -> None:
        start = self._start
        if start is None:
            return
        end_x, end_y = self._global_point(surface, x, y)
        rect = rect_from_drag(start[0], start[1], end_x, end_y)
        self._finish(rect if rect.is_usable() else None)

    def _update_drag(self, end_x: float, end_y: float) -> None:
        start = self._start
        if start is None:
            return
        left = min(start[0], end_x)
        top = min(start[1], end_y)
        right = max(start[0], end_x)
        bottom = max(start[1], end_y)
        label = windows_region_size_label(start[0], start[1], end_x, end_y)
        for surface in self._surfaces:
            scale = max(1.0, surface.scale)
            window = surface.window
            window.setProperty("selectionActive", True)
            window.setProperty("selectionX", (left - surface.screen.x) / scale)
            window.setProperty("selectionY", (top - surface.screen.y) / scale)
            window.setProperty("selectionWidth", (right - left) / scale)
            window.setProperty("selectionHeight", (bottom - top) / scale)
            contains = _screen_contains_point(surface.screen, end_x, end_y)
            window.setProperty("showSize", contains)
            if contains:
                logical_width = surface.screen.width / scale
                logical_height = surface.screen.height / scale
                window.setProperty(
                    "sizeX",
                    min(max((end_x - surface.screen.x) / scale + 12, 12), logical_width - 112),
                )
                window.setProperty(
                    "sizeY",
                    min(max((end_y - surface.screen.y) / scale + 12, 12), logical_height - 42),
                )
                window.setProperty("sizeLabel", label)

    def _finish(self, rect: ScreenRect | None) -> None:
        surfaces = self._surfaces
        callback = self._on_complete
        self._surfaces = []
        self._on_complete = None
        self._start = None
        for surface in surfaces:
            self._runtime.destroy_window(surface.window)
        if callback is not None:
            self._runtime.call_later(40, lambda: callback(rect))


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

    def set_stop(self, on_stop: Callable[[], None] | None) -> None:
        self._on_stop = on_stop

    def set_anchor(self, rect: ScreenRect | None) -> None:
        self._anchor = rect
        self._runtime.call_soon(self._position)

    def show_status(self, message: str, source: str | None = None) -> None:
        del source
        self._runtime.call_soon(lambda: self._show(format_live_status(message)))

    def show(self, job: TranslateJob) -> None:
        self._runtime.call_soon(lambda: self._show(format_live_overlay(job)))

    def hide(self) -> None:
        self._runtime.call_soon(self._hide)

    def _create(self) -> None:
        window = self._runtime.create_window("LiveOverlay.qml")
        self._runtime.connect_signal(window, "stopRequested()", self._stop)
        self._window = window

    def _show(self, content: OverlayContent) -> None:
        if self._window is None:
            self._create()
        assert self._window is not None
        metadata = content.title.removeprefix("实时 · ").removeprefix("实时")
        source = content.source
        translation = content.translation
        if not source and translation:
            metadata = translation
            translation = ""
        self._window.setProperty("metadataText", metadata)
        self._window.setProperty("sourceText", source)
        self._window.setProperty("translationText", translation)
        self._position()
        self._runtime.present_window(self._window)
        self._runtime.set_no_activate(self._window)

    def _position(self) -> None:
        window = self._window
        anchor = self._anchor
        if window is None or anchor is None:
            return
        screen = windows_virtual_screen_rect()
        base = windows_live_overlay_rect(anchor, screen=screen)
        scale = self._runtime.device_pixel_ratio(window)
        window.setWidth(max(280, round(base.width / scale)))
        self._runtime.process_events()
        requested = float(window.property("desiredHeight") or 120.0) * scale
        height = windows_live_overlay_height(
            requested,
            screen_height=screen.height,
            scale=scale,
        )
        rect = windows_live_overlay_rect(anchor, screen=screen, bar_height=height)
        self._runtime.set_native_rect(window, rect)

    def _hide(self) -> None:
        if self._window is not None:
            self._runtime.hide_window(self._window)

    def _stop(self) -> None:
        self._hide()
        callback = self._on_stop
        if callback is not None:
            threading.Thread(target=callback, daemon=True).start()


class WindowsSettingsPresenter:
    def __init__(
        self,
        runtime: WindowsUiRuntime,
        *,
        load: Callable[[], AppPreferences],
        save: Callable[[AppPreferences], None],
    ) -> None:
        self._runtime = runtime
        self._load = load
        self._save = save
        self._window: object | None = None

    def show(self) -> None:
        self._runtime.call_soon(self._show_ui)

    def _create(self) -> None:
        window = self._runtime.create_window("Settings.qml")
        self._runtime.connect_signal(
            window,
            "commitRequested(bool)",
            self._commit,
        )
        self._window = window

    def _show_ui(self) -> None:
        if self._window is None:
            self._create()
        try:
            preferences = self._load()
        except Exception as exc:
            self._set_status(f"读取设置失败：{exc}")
            return
        self._fill(preferences)
        assert self._window is not None
        self._runtime.center_window(self._window)
        self._runtime.present_window(self._window)

    def _fill(self, preferences: AppPreferences) -> None:
        assert self._window is not None
        provider_labels = dict(PROVIDER_OPTIONS)
        engine_labels = dict(_WINDOWS_ENGINE_OPTIONS)
        tier_labels = dict(LOCAL_ADVANCED_MODEL_TIER_OPTIONS)
        image_labels = dict(IMAGE_MODE_OPTIONS)
        source_labels = dict(SOURCE_LANG_OPTIONS)
        target_labels = dict(TARGET_LANG_OPTIONS)
        models: dict[str, list[str]] = {
            "translateProviderOptions": [label for _value, label in PROVIDER_OPTIONS],
            "translateModelOptions": list(preferences.translate_model_choices),
            "ocrEngineOptions": [label for _value, label in _WINDOWS_ENGINE_OPTIONS],
            "localTierOptions": [label for _value, label in LOCAL_ADVANCED_MODEL_TIER_OPTIONS],
            "ocrModelOptions": list(preferences.ocr_model_choices),
            "imageModeOptions": [label for _value, label in IMAGE_MODE_OPTIONS],
            "sourceLanguageOptions": [label for _value, label in SOURCE_LANG_OPTIONS],
            "targetLanguageOptions": [label for _value, label in TARGET_LANG_OPTIONS],
        }
        values: dict[str, str] = {
            "translateProvider": provider_labels.get(
                preferences.translate_provider,
                preferences.translate_provider,
            ),
            "translateBaseUrl": preferences.translate_base_url,
            "translateApiKey": preferences.translate_api_key,
            "translateModel": preferences.translate_model,
            "translateRegion": preferences.translate_region,
            "ocrEngine": engine_labels.get(preferences.ocr_engine, engine_labels["auto"]),
            "localTier": tier_labels.get(
                preferences.ocr_local_advanced_model_tier,
                preferences.ocr_local_advanced_model_tier,
            ),
            "ocrStandardApiKey": preferences.ocr_standard_api_key,
            "ocrBaseUrl": preferences.ocr_base_url,
            "ocrApiKey": preferences.ocr_api_key,
            "ocrModel": preferences.ocr_model,
            "ocrMinConfidence": f"{preferences.ocr_min_confidence:g}",
            "imageMode": image_labels.get(
                preferences.ocr_image_mode,
                preferences.ocr_image_mode,
            ),
            "sourceLanguage": source_labels.get(
                preferences.source_lang,
                preferences.source_lang,
            ),
            "targetLanguage": target_labels.get(
                preferences.target_lang,
                preferences.target_lang,
            ),
            "selectionHotkey": preferences.hotkey_selection,
            "ocrHotkey": preferences.hotkey_ocr,
            "liveHotkey": preferences.hotkey_live_ocr,
        }
        for name, value in {**models, **values}.items():
            self._window.setProperty(name, value)
        self._set_status("")

    def _commit(self, close_after_save: bool) -> None:
        assert self._window is not None
        provider_values = {label: value for value, label in PROVIDER_OPTIONS}
        engine_values = {label: value for value, label in _WINDOWS_ENGINE_OPTIONS}
        tier_values = {label: value for value, label in LOCAL_ADVANCED_MODEL_TIER_OPTIONS}
        image_values = {label: value for value, label in IMAGE_MODE_OPTIONS}
        source_values = {label: value for value, label in SOURCE_LANG_OPTIONS}
        target_values = {label: value for value, label in TARGET_LANG_OPTIONS}

        def value(name: str) -> str:
            return str(self._window.property(name) or "")

        try:
            preferences = parse_settings_form(
                ocr_engine=engine_values.get(value("ocrEngine"), value("ocrEngine")),
                ocr_local_advanced_model_tier=tier_values.get(value("localTier"), value("localTier")),
                ocr_min_confidence=value("ocrMinConfidence"),
                ocr_image_mode=image_values.get(value("imageMode"), value("imageMode")),
                source_lang=source_values.get(value("sourceLanguage"), value("sourceLanguage")),
                target_lang=target_values.get(value("targetLanguage"), value("targetLanguage")),
                hotkey_selection=value("selectionHotkey"),
                hotkey_ocr=value("ocrHotkey"),
                hotkey_live_ocr=value("liveHotkey"),
                translate_model=value("translateModel"),
                ocr_model=value("ocrModel"),
                translate_base_url=value("translateBaseUrl"),
                ocr_base_url=value("ocrBaseUrl"),
                translate_api_key=value("translateApiKey"),
                ocr_api_key=value("ocrApiKey"),
                ocr_standard_api_key=value("ocrStandardApiKey"),
                translate_provider=provider_values.get(
                    value("translateProvider"),
                    value("translateProvider"),
                ),
                translate_region=value("translateRegion"),
            )
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self._set_busy(True)
        self._set_status("正在保存…")

        def run() -> None:
            try:
                self._save(preferences)
            except Exception as exc:
                self._runtime.call_soon(
                    lambda: self._saved(error=str(exc), close_after_save=False)
                )
                return
            self._runtime.call_soon(
                lambda: self._saved(error=None, close_after_save=bool(close_after_save))
            )

        threading.Thread(target=run, daemon=True).start()

    def _saved(self, *, error: str | None, close_after_save: bool) -> None:
        self._set_busy(False)
        if error is not None:
            self._set_status(f"保存失败：{error}")
            return
        self._set_status("已应用", success=True)
        if close_after_save and self._window is not None:
            self._runtime.hide_window(self._window)

    def _set_busy(self, busy: bool) -> None:
        if self._window is not None:
            self._window.setProperty("busy", busy)

    def _set_status(self, text: str, *, success: bool = False) -> None:
        if self._window is None:
            return
        self._window.setProperty("statusText", text)
        self._window.setProperty("statusSuccess", success)


class WindowsTray:
    def __init__(
        self,
        *,
        runtime: WindowsUiRuntime,
        listener: object,
        open_settings: Callable[[], None] | None,
        open_input: Callable[[], None] | None,
        quit_app: Callable[[], None],
    ) -> None:
        self._runtime = runtime
        self._listener = listener
        self._open_settings = open_settings
        self._open_input = open_input
        self._quit_app = quit_app
        self._icon: object | None = None
        self._menu: object | None = None
        self._actions: dict[str, object] = {}

    def start(self) -> None:
        from PySide6.QtGui import QAction, QIcon
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon

        menu = QMenu()
        selection = QAction(menu)
        screenshot = QAction(menu)
        live = QAction(menu)
        workspace = QAction("打开翻译工作区…", menu)
        settings = QAction("设置…", menu)
        quit_action = QAction("退出 AI Translate", menu)
        selection.triggered.connect(
            lambda: _start_callback(self._listener.handle_selection)
        )
        screenshot.triggered.connect(lambda: _start_callback(self._listener.handle_ocr))
        live.triggered.connect(lambda: _start_callback(self._listener.handle_live_ocr))
        workspace.triggered.connect(lambda: self._invoke_ui(self._open_input))
        settings.triggered.connect(lambda: self._invoke_ui(self._open_settings))
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(selection)
        menu.addAction(screenshot)
        menu.addAction(live)
        menu.addSeparator()
        menu.addAction(workspace)
        menu.addAction(settings)
        menu.addAction(quit_action)
        menu.aboutToShow.connect(self._refresh_labels)

        icon = QSystemTrayIcon(QIcon(str(_APP_ICON)), self._runtime.app)
        icon.setToolTip("AI Translate")
        icon.setContextMenu(menu)

        def activated(reason: object) -> None:
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self._invoke_ui(self._open_input)

        icon.activated.connect(activated)
        self._menu = menu
        self._icon = icon
        self._actions = {
            "selection": selection,
            "screenshot": screenshot,
            "live": live,
        }
        self._refresh_labels()
        icon.show()

    def stop(self) -> None:
        icon = self._icon
        menu = self._menu
        self._icon = None
        self._menu = None
        self._actions = {}
        if icon is not None:
            icon.hide()
            icon.deleteLater()
        if menu is not None:
            menu.deleteLater()

    def _refresh_labels(self) -> None:
        if not self._actions:
            return
        self._actions["selection"].setText(
            f"划词翻译 · {windows_hotkey_label(self._listener.selection_hotkey)}"
        )
        self._actions["screenshot"].setText(
            f"截图翻译 · {windows_hotkey_label(self._listener.ocr_hotkey)}"
        )
        self._actions["live"].setText(
            "停止实时翻译"
            if self._listener.live_running
            else f"开始实时翻译 · {windows_hotkey_label(self._listener.live_hotkey)}"
        )

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
            runtime=runtime,
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
            runtime.show_error("AI Translate", str(exc))
            return 2
    finally:
        if tray is not None:
            tray.stop()
        release_instance()


def windows_settings_engine_options() -> tuple[tuple[str, str], ...]:
    return _WINDOWS_ENGINE_OPTIONS


def windows_settings_model_tier_options() -> tuple[tuple[str, str], ...]:
    return LOCAL_ADVANCED_MODEL_TIER_OPTIONS


def _screen_contains_point(screen: ScreenRect, x: float, y: float) -> bool:
    canonical = screen.canonical()
    return (
        canonical.x <= x < canonical.x + canonical.width
        and canonical.y <= y < canonical.y + canonical.height
    )


def _qt_window_handle(window: object) -> int:
    return int(window.winId())


def _set_qt_window_topmost(window: object, *, topmost: bool) -> None:
    if sys.platform != "win32":
        return
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
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
    insert_after = wintypes.HWND(-1 if topmost else -2)
    user32.SetWindowPos(
        _qt_window_handle(window),
        insert_after,
        0,
        0,
        0,
        0,
        0x0001 | 0x0002 | 0x0010,
    )


def _set_qt_window_no_activate(window: object) -> None:
    if sys.platform != "win32":
        return
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    get_window_long = user32.GetWindowLongW
    set_window_long = user32.SetWindowLongW
    get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_window_long.restype = ctypes.c_long
    set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    set_window_long.restype = ctypes.c_long
    hwnd = _qt_window_handle(window)
    style = int(get_window_long(hwnd, -20))
    set_window_long(hwnd, -20, style | 0x08000000)
    _set_qt_window_topmost(window, topmost=True)


def _set_qt_window_rect(window: object, rect: ScreenRect) -> None:
    if sys.platform != "win32":
        canonical = rect.canonical()
        window.setGeometry(
            round(canonical.x),
            round(canonical.y),
            max(1, round(canonical.width)),
            max(1, round(canonical.height)),
        )
        return
    from ctypes import wintypes

    canonical = rect.canonical()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
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
    ok = user32.SetWindowPos(
        _qt_window_handle(window),
        wintypes.HWND(-1),
        round(canonical.x),
        round(canonical.y),
        max(1, round(canonical.width)),
        max(1, round(canonical.height)),
        0x0010 | 0x0040,
    )
    if not ok:
        raise OSError(ctypes.get_last_error(), "SetWindowPos failed")


def _run_callback(callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception as exc:
        print(f"Windows desktop action failed: {exc}", file=sys.stderr)


def _start_callback(callback: Callable[[], None]) -> None:
    threading.Thread(target=_run_callback, args=(callback,), daemon=True).start()
