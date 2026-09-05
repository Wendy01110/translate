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
    return bool(args) and args[0] in {"ocr", "ocr-translate", "text", "listen", "app"}


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
    *,
    live_presenter: ResultPresenter | None = None,
    live_active: Callable[[], bool] | None = None,
) -> Callable[[str], None]:
    def notify(model: str) -> None:
        target = presenter
        if (
            live_presenter is not None
            and live_active is not None
            and live_active()
        ):
            target = live_presenter
        target.show_status(paddle_first_load_message(model))

    return notify


def _save_preferences(
    prefs: AppPreferences,
    *,
    listener: DesktopListener,
    presenter: ResultPresenter,
    on_paddle_first_load: Callable[[str], None],
) -> None:
    upsert_env_values(resolve_env_path(), prefs.to_env())
    refreshed = Settings.load()
    listener.replace_runtime(
        selection=selection_service(refreshed),
        ocr_translate=ocr_translate_service(
            refreshed,
            on_paddle_first_load=on_paddle_first_load,
        ),
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
    cli_ocr = None
    cli_ocr_translate = None
    cli_selection = None
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
        listener = DesktopListener(
            selection=selection_service(settings),
            ocr_translate=ocr_translate_service(
                settings,
                on_paddle_first_load=paddle_first_load,
            ),
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
        )
        presenter.set_translate(listener.handle_typed_text)
        presenter.configure_target_languages(
            TARGET_LANG_OPTIONS,
            current=settings.translate.target_lang,
            on_change=listener.set_target_lang,
        )
        live_ui.set_stop(listener.stop_live)
        if command == "app":
            settings_ui = SettingsPresenter(
                load=lambda: Settings.load().preferences(),
                save=lambda prefs: _save_preferences(
                    prefs,
                    listener=listener,
                    presenter=presenter,
                    on_paddle_first_load=paddle_first_load,
                ),
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
    else:
        cli_ocr = ocr_engine(settings)
        cli_ocr_translate = ocr_translate_service(settings)
        cli_selection = selection_service(settings)
    return CliServices(
        ocr=cli_ocr,
        ocr_translate=cli_ocr_translate,
        selection=cli_selection,
        load_image=load_image_file,
        capture_region=region_screenshot.capture_region,
        read_selected_text=selected_text.read_selected_text,
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
        settings_ui = WindowsSettingsPresenter(
            runtime,
            load=lambda: Settings.load().preferences(),
            save=lambda prefs: _save_preferences(
                prefs,
                listener=listener,
                presenter=presenter,
                on_paddle_first_load=paddle_first_load,
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
