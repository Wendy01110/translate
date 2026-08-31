from __future__ import annotations

import sys
from collections.abc import Callable, Sequence

from ai_translate.bootstrap.composition import (
    config_status,
    ocr_engine,
    ocr_translate_service,
    selection_service,
)
from ai_translate.config import AppPreferences, Settings, resolve_env_path
from ai_translate.core.ports import ResultPresenter
from ai_translate.infrastructure.env_file import upsert_env_values
from ai_translate.infrastructure.image_file import load_image_file
from ai_translate.interfaces.cli import CliServices, run
from ai_translate.interfaces.listen import DesktopListener
from ai_translate.interfaces.overlay import paddle_first_load_message


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    settings = Settings.load()
    status = config_status(settings)
    services = None
    if _needs_runtime(args):
        services = _build_services(settings, args)
    return run(args, status, services)


def _needs_runtime(args: Sequence[str]) -> bool:
    return any(arg in {"ocr", "ocr-translate", "text", "listen", "app"} for arg in args)


def _build_services(settings: Settings, args: Sequence[str]) -> CliServices:
    if sys.platform == "win32" and _needs_windows_ui(args):
        return _build_windows_services(settings, args)
    if sys.platform == "darwin":
        return _build_macos_services(settings, args)
    return _common_services(settings)


def _common_services(settings: Settings) -> CliServices:
    return CliServices(
        ocr=ocr_engine(settings),
        ocr_translate=ocr_translate_service(settings),
        selection=selection_service(settings),
        load_image=load_image_file,
        source_lang=settings.translate.source_lang,
        target_lang=settings.translate.target_lang,
    )


def _paddle_first_load_notifier(
    presenter: ResultPresenter,
) -> Callable[[str], None]:
    return lambda model: presenter.show_status(paddle_first_load_message(model))


def _build_macos_services(settings: Settings, args: Sequence[str]) -> CliServices:
    from ai_translate.infrastructure.screenshot import RectCapture, RegionScreenshot
    from ai_translate.infrastructure.selected_text import (
        SelectedTextSource,
        accessibility_trusted,
        request_accessibility_prompt,
    )
    from ai_translate.interfaces.live_overlay import LiveOverlayPresenter
    from ai_translate.interfaces.menubar import cocoa_app_loop, run_status_app
    from ai_translate.interfaces.overlay import OverlayPresenter
    from ai_translate.interfaces.region_picker import RegionPicker
    from ai_translate.interfaces.settings import (
        TARGET_LANG_OPTIONS,
        SettingsPresenter,
    )

    start_listener = None
    start_app = None
    if "listen" in args or "app" in args:
        live_ui = LiveOverlayPresenter()
        presenter = OverlayPresenter()
        paddle_first_load = _paddle_first_load_notifier(presenter)
        listener = DesktopListener(
            selection=selection_service(settings),
            ocr_translate=ocr_translate_service(
                settings,
                on_paddle_first_load=paddle_first_load,
            ),
            read_selected_text=SelectedTextSource().read_selected_text,
            capture_region=RegionScreenshot().capture_region,
            presenter=presenter,
            selection_hotkey=settings.hotkey.selection,
            ocr_hotkey=settings.hotkey.ocr,
            source_lang=settings.translate.source_lang,
            target_lang=settings.translate.target_lang,
            event_loop=cocoa_app_loop if "app" in args else None,
            accessibility_ready=accessibility_trusted,
            permission_prompt=(
                request_accessibility_prompt if "app" in args else None
            ),
            live_hotkey=settings.hotkey.live_ocr,
            pick_region=RegionPicker(),
            capture_rect=RectCapture().capture_rect,
            live_presenter=live_ui,
        )
        presenter.set_translate(listener.handle_typed_text)
        presenter.configure_target_languages(
            TARGET_LANG_OPTIONS,
            current=settings.translate.target_lang,
            on_change=listener.set_target_lang,
        )
        live_ui.set_stop(listener.stop_live)
        if "app" in args:
            def save_preferences(prefs: AppPreferences) -> None:
                upsert_env_values(resolve_env_path(), prefs.to_env())
                refreshed = Settings.load()
                listener.replace_runtime(
                    selection=selection_service(refreshed),
                    ocr_translate=ocr_translate_service(
                        refreshed,
                        on_paddle_first_load=paddle_first_load,
                    ),
                    source_lang=refreshed.translate.source_lang,
                    target_lang=refreshed.translate.target_lang,
                    selection_hotkey=refreshed.hotkey.selection,
                    ocr_hotkey=refreshed.hotkey.ocr,
                    live_hotkey=refreshed.hotkey.live_ocr,
                )
                presenter.set_target_language(refreshed.translate.target_lang)

            settings_ui = SettingsPresenter(
                load=lambda: Settings.load().preferences(),
                save=save_preferences,
            )

            def start_app_run() -> int:
                return run_status_app(
                    listener,
                    open_settings=settings_ui.show,
                    open_input=presenter.show_input,
                )

            start_app = start_app_run
        else:
            start_listener = listener.run
    return CliServices(
        ocr=ocr_engine(settings),
        ocr_translate=ocr_translate_service(settings),
        selection=selection_service(settings),
        load_image=load_image_file,
        capture_region=RegionScreenshot().capture_region,
        read_selected_text=SelectedTextSource().read_selected_text,
        start_listener=start_listener,
        start_app=start_app,
        source_lang=settings.translate.source_lang,
        target_lang=settings.translate.target_lang,
    )


def _build_windows_services(settings: Settings, args: Sequence[str]) -> CliServices:
    from ai_translate.infrastructure.selected_text import SelectedTextSource
    from ai_translate.infrastructure.windows_desktop import (
        WindowsClipboard,
        WindowsInstanceLock,
        WindowsRectCapture,
        WindowsRegionScreenshot,
        send_windows_copy_key,
    )
    from ai_translate.interfaces.windows_desktop import (
        WindowsHotkeyListener,
        WindowsLiveOverlayPresenter,
        WindowsOverlayPresenter,
        WindowsRegionPicker,
        WindowsUiRuntime,
        run_windows_status_app,
    )
    from ai_translate.interfaces.windows_views import (
        WindowsInputTranslatePresenter,
        WindowsSettingsPresenter,
    )

    runtime = WindowsUiRuntime()
    picker = WindowsRegionPicker(runtime)
    rect_capture = WindowsRectCapture()
    region_capture = WindowsRegionScreenshot(
        pick_region=picker,
        capture_rect=rect_capture.capture_rect,
    )
    if "listen" not in args and "app" not in args:
        return CliServices(
            ocr=ocr_engine(settings),
            ocr_translate=ocr_translate_service(settings),
            selection=selection_service(settings),
            load_image=load_image_file,
            capture_region=region_capture.capture_region,
            source_lang=settings.translate.source_lang,
            target_lang=settings.translate.target_lang,
        )

    clipboard = WindowsClipboard()
    selected_text = SelectedTextSource(
        clipboard_read=clipboard.read,
        clipboard_write=clipboard.write,
        copy_selection=send_windows_copy_key,
        can_simulate_copy=lambda: True,
        fallback_to_saved_clipboard=True,
    )
    presenter = WindowsOverlayPresenter(runtime)
    live_ui = WindowsLiveOverlayPresenter(runtime)
    paddle_first_load = _paddle_first_load_notifier(presenter)
    listener = DesktopListener(
        selection=selection_service(settings),
        ocr_translate=ocr_translate_service(
            settings,
            on_paddle_first_load=paddle_first_load,
        ),
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
    )
    live_ui.set_stop(listener.stop_live)
    start_listener = listener.run if "listen" in args else None
    start_app = None
    if "app" in args:

        def save_preferences(prefs: AppPreferences) -> None:
            upsert_env_values(resolve_env_path(), prefs.to_env())
            refreshed = Settings.load()
            listener.replace_runtime(
                selection=selection_service(refreshed),
                ocr_translate=ocr_translate_service(
                    refreshed,
                    on_paddle_first_load=paddle_first_load,
                ),
                source_lang=refreshed.translate.source_lang,
                target_lang=refreshed.translate.target_lang,
                selection_hotkey=refreshed.hotkey.selection,
                ocr_hotkey=refreshed.hotkey.ocr,
                live_hotkey=refreshed.hotkey.live_ocr,
            )

        settings_ui = WindowsSettingsPresenter(
            runtime,
            load=lambda: Settings.load().preferences(),
            save=save_preferences,
        )
        input_ui = WindowsInputTranslatePresenter(
            runtime,
            translate=listener.handle_typed_text,
        )
        instance = WindowsInstanceLock()

        def start_app_run() -> int:
            return run_windows_status_app(
                listener,
                runtime=runtime,
                acquire_instance=instance.acquire,
                release_instance=instance.close,
                open_settings=settings_ui.show,
                open_input=input_ui.show,
            )

        start_app = start_app_run
    return CliServices(
        ocr=ocr_engine(settings),
        ocr_translate=ocr_translate_service(settings),
        selection=selection_service(settings),
        load_image=load_image_file,
        capture_region=region_capture.capture_region,
        read_selected_text=selected_text.read_selected_text,
        start_listener=start_listener,
        start_app=start_app,
        source_lang=settings.translate.source_lang,
        target_lang=settings.translate.target_lang,
    )


def _needs_windows_ui(args: Sequence[str]) -> bool:
    return any(arg in {"listen", "app", "--screenshot"} for arg in args)


if __name__ == "__main__":
    raise SystemExit(main())
