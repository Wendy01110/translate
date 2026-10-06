from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import replace

from ai_translate.bootstrap.composition import (
    DesktopRuntime,
    config_status,
    ocr_engine,
    ocr_translate_service,
    selection_service,
)
from ai_translate.config import AppPreferences, Settings, resolve_env_path
from ai_translate.core.history import HistoryEntry
from ai_translate.core.models import JobKind, JobStatus, TranslateJob
from ai_translate.core.ports import ResultPresenter
from ai_translate.infrastructure.env_file import upsert_env_values
from ai_translate.infrastructure.image_file import load_image_file
from ai_translate.interfaces.cli import CliServices, run
from ai_translate.interfaces.listen import DesktopListener
from ai_translate.interfaces.overlay import paddle_first_load_message


def _desktop_history():
    from ai_translate.features.history import TranslationHistory
    from ai_translate.infrastructure.history import JsonHistoryStore, default_history_path

    return TranslationHistory(JsonHistoryStore(default_history_path()))


def _restore_history(
    entry: HistoryEntry, listener: DesktopListener, presenter: ResultPresenter,
) -> bool:
    if listener.translation_busy or getattr(presenter, "translation_busy", False):
        return False
    listener.set_target_lang(entry.target_lang)
    presenter.set_target_language(entry.target_lang)
    presenter.show(TranslateJob(
        kind=entry.kind, status=JobStatus.SUCCESS,
        source_text=entry.source_text, translated_text=entry.translated_text,
        ocr_text=entry.source_text if entry.kind is JobKind.OCR else None,
    ))
    return True


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    settings = Settings.load()
    status = config_status(settings)
    services = None
    if _needs_runtime(args):
        services = _build_services(settings, args)
    return run(args, status, services)


def _needs_runtime(args: Sequence[str]) -> bool:
    return bool(args) and args[0] in {"ocr", "ocr-translate", "text", "listen", "app"}


def _build_services(settings: Settings, args: Sequence[str]) -> CliServices:
    if sys.platform == "win32" and _needs_windows_ui(args):
        return _build_windows_services(settings, args)
    if sys.platform == "darwin":
        return _build_macos_services(settings, args)
    return _common_services(settings, args)


def _common_services(settings: Settings, args: Sequence[str]) -> CliServices:
    command = args[0] if args else ""
    return CliServices(
        ocr=ocr_engine(settings) if command == "ocr" else None,
        ocr_translate=(
            ocr_translate_service(settings) if command == "ocr-translate" else None
        ),
        selection=selection_service(settings) if command == "text" else None,
        load_image=load_image_file,
        source_lang=settings.translate.source_lang,
        target_lang=settings.translate.target_lang,
    )


def _paddle_first_load_notifier(
    presenter: ResultPresenter,
    *,
    live_presenter: ResultPresenter | None = None,
    live_active: Callable[[], bool] | None = None,
) -> Callable[[str], None]:
    def notify(model: str) -> None:
        if (
            live_presenter is not None
            and live_active is not None
            and live_active()
        ):
            live_presenter.show_status(paddle_first_load_message(model, compact=True))
            return
        presenter.show_status(paddle_first_load_message(model))

    return notify


def _save_preferences(
    prefs: AppPreferences,
    *,
    listener: DesktopListener,
    presenter: ResultPresenter,
    services: DesktopRuntime,
) -> None:
    upsert_env_values(resolve_env_path(), prefs.to_env())
    refreshed = Settings.load()
    services.update(refreshed)
    listener.replace_runtime(
        selection=services.selection,
        ocr_translate=services.ocr_translate,
        source_lang=refreshed.translate.source_lang,
        target_lang=refreshed.translate.target_lang,
        selection_hotkey=refreshed.hotkey.selection,
        ocr_hotkey=refreshed.hotkey.ocr,
        live_hotkey=refreshed.hotkey.live_ocr,
    )
    presenter.set_target_language(refreshed.translate.target_lang)


def _build_macos_services(settings: Settings, args: Sequence[str]) -> CliServices:
    from ai_translate.infrastructure.screenshot import RectCapture, RegionScreenshot
    from ai_translate.infrastructure.selected_text import (
        SelectedTextSource,
        accessibility_trusted,
        request_accessibility_prompt,
    )
    from ai_translate.interfaces.live_overlay import LiveOverlayPresenter
    from ai_translate.interfaces.history import HistoryPresenter
    from ai_translate.interfaces.menubar import cocoa_app_loop, run_status_app
    from ai_translate.interfaces.overlay import OverlayPresenter
    from ai_translate.interfaces.region_picker import RegionPicker
    from ai_translate.interfaces.settings import (
        TARGET_LANG_OPTIONS,
        SettingsPresenter,
    )

    selected_text = SelectedTextSource()
    region_screenshot = RegionScreenshot()
    command = args[0] if args else ""
    start_listener = None
    start_app = None
    if command in {"listen", "app"}:
        live_ui = LiveOverlayPresenter()
        presenter = OverlayPresenter()
        listener: DesktopListener | None = None
        paddle_first_load = _paddle_first_load_notifier(
            presenter,
            live_presenter=live_ui,
            live_active=lambda: bool(listener and listener.live_running),
        )
        desktop_services = DesktopRuntime(settings, on_paddle_first_load=paddle_first_load)
        history = _desktop_history()
        listener = DesktopListener(
            selection=desktop_services.selection,
            ocr_translate=desktop_services.ocr_translate,
            read_selected_text=selected_text.read_selected_text,
            capture_region=region_screenshot.capture_region,
            presenter=presenter,
            selection_hotkey=settings.hotkey.selection,
            ocr_hotkey=settings.hotkey.ocr,
            source_lang=settings.translate.source_lang,
            target_lang=settings.translate.target_lang,
            event_loop=cocoa_app_loop if command == "app" else None,
            accessibility_ready=accessibility_trusted,
            permission_prompt=(
                request_accessibility_prompt if command == "app" else None
            ),
            live_hotkey=settings.hotkey.live_ocr,
            pick_region=RegionPicker(),
            capture_rect=RectCapture().capture_rect,
            live_presenter=live_ui,
            record_result=history.record,
        )
        presenter.set_translate(listener.handle_typed_text)
        presenter.configure_target_languages(
            TARGET_LANG_OPTIONS,
            current=settings.translate.target_lang,
            on_change=listener.set_target_lang,
        )
        live_ui.set_stop(listener.stop_live)
        if command == "app":
            history_ui = HistoryPresenter(
                history, lambda entry: _restore_history(entry, listener, presenter),
            )
            settings_ui = SettingsPresenter(
                load=lambda: Settings.load().preferences(),
                save=lambda prefs: _save_preferences(
                    prefs,
                    listener=listener,
                    presenter=presenter,
                    services=desktop_services,
                ),
            )

            def start_app_run() -> int:
                return run_status_app(
                    listener,
                    open_settings=settings_ui.show,
                    open_input=presenter.show_input,
                    open_history=history_ui.show,
                )

            start_app = start_app_run
        else:
            start_listener = listener.run
    else:
        return replace(
            _common_services(settings, args),
            capture_region=region_screenshot.capture_region,
            read_selected_text=selected_text.read_selected_text,
        )
    return CliServices(
        load_image=load_image_file,
        capture_region=region_screenshot.capture_region,
        read_selected_text=selected_text.read_selected_text,
        start_listener=start_listener,
        start_app=start_app,
        source_lang=settings.translate.source_lang,
        target_lang=settings.translate.target_lang,
    )


def _build_windows_services(settings: Settings, args: Sequence[str]) -> CliServices:
    from ai_translate.interfaces.history import WindowsHistoryPresenter
    from ai_translate.infrastructure.selected_text import SelectedTextSource
    from ai_translate.infrastructure.windows_desktop import (
        WindowsClipboard,
        WindowsInstanceLock,
        WindowsRectCapture,
        WindowsRegionScreenshot,
        send_windows_copy_key,
        windows_clipboard_owned_by_foreground,
    )
    from ai_translate.interfaces.windows_desktop import WindowsHotkeyListener
    from ai_translate.interfaces.windows_qt import (
        WindowsLiveOverlayPresenter,
        WindowsOverlayPresenter,
        WindowsRegionPicker,
        WindowsSettingsPresenter,
        WindowsUiRuntime,
        run_windows_status_app,
    )
    from ai_translate.interfaces.settings import TARGET_LANG_OPTIONS

    runtime = WindowsUiRuntime()
    picker = WindowsRegionPicker(runtime)
    rect_capture = WindowsRectCapture()
    region_capture = WindowsRegionScreenshot(
        pick_region=picker,
        capture_rect=rect_capture.capture_rect,
    )
    command = args[0] if args else ""
    if command not in {"listen", "app"}:
        return replace(
            _common_services(settings, args),
            capture_region=region_capture.capture_region,
        )

    clipboard = WindowsClipboard()
    selected_text = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=send_windows_copy_key,
        can_simulate_copy=lambda: True,
        fallback_to_saved_clipboard=True,
        can_use_saved_clipboard=windows_clipboard_owned_by_foreground,
    )
    presenter = WindowsOverlayPresenter(runtime)
    live_ui = WindowsLiveOverlayPresenter(runtime)
    listener: DesktopListener | None = None
    paddle_first_load = _paddle_first_load_notifier(
        presenter,
        live_presenter=live_ui,
        live_active=lambda: bool(listener and listener.live_running),
    )
    desktop_services = DesktopRuntime(settings, on_paddle_first_load=paddle_first_load)
    history = _desktop_history()
    listener = DesktopListener(
        selection=desktop_services.selection,
        ocr_translate=desktop_services.ocr_translate,
        read_selected_text=selected_text.read_selected_text,
        capture_region=region_capture.capture_region,
        presenter=presenter,
        selection_hotkey=settings.hotkey.selection,
        ocr_hotkey=settings.hotkey.ocr,
        source_lang=settings.translate.source_lang,
        target_lang=settings.translate.target_lang,
        hotkey_factory=WindowsHotkeyListener,
        event_loop=runtime.run,
        accessibility_ready=lambda: True,
        live_hotkey=settings.hotkey.live_ocr,
        pick_region=picker,
        capture_rect=rect_capture.capture_rect,
        live_presenter=live_ui,
        record_result=history.record,
    )
    presenter.set_translate(listener.handle_typed_text)
    presenter.configure_target_languages(
        TARGET_LANG_OPTIONS,
        current=settings.translate.target_lang,
        on_change=listener.set_target_lang,
    )
    live_ui.set_stop(listener.stop_live)
    start_listener = listener.run if command == "listen" else None
    start_app = None
    if command == "app":
        history_ui = WindowsHistoryPresenter(
            runtime, history, lambda entry: _restore_history(entry, listener, presenter),
        )
        settings_ui = WindowsSettingsPresenter(
            runtime,
            load=lambda: Settings.load().preferences(),
            save=lambda prefs: _save_preferences(
                prefs,
                listener=listener,
                presenter=presenter,
                services=desktop_services,
            ),
        )
        instance = WindowsInstanceLock()

        def start_app_run() -> int:
            return run_windows_status_app(
                listener,
                runtime=runtime,
                acquire_instance=instance.acquire,
                release_instance=instance.close,
                open_settings=settings_ui.show,
                open_input=presenter.show_input,
                open_history=history_ui.show,
            )

        start_app = start_app_run
    return CliServices(
        load_image=load_image_file,
        capture_region=region_capture.capture_region,
        read_selected_text=selected_text.read_selected_text,
        start_listener=start_listener,
        start_app=start_app,
        source_lang=settings.translate.source_lang,
        target_lang=settings.translate.target_lang,
    )


def _needs_windows_ui(args: Sequence[str]) -> bool:
    if not args:
        return False
    command = args[0]
    return command in {"listen", "app"} or (
        command in {"ocr", "ocr-translate"} and "--screenshot" in args[1:]
    )


if __name__ == "__main__":
    raise SystemExit(main())
