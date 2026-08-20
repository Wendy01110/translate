from __future__ import annotations

import sys
from collections.abc import Sequence

from ai_translate.bootstrap.composition import (
    config_status,
    ocr_engine,
    ocr_translate_service,
    selection_service,
)
from ai_translate.config import AppPreferences, Settings, resolve_env_path
from ai_translate.infrastructure.env_file import upsert_env_values
from ai_translate.infrastructure.image_file import load_image_file
from ai_translate.infrastructure.screenshot import RectCapture, RegionScreenshot
from ai_translate.infrastructure.selected_text import (
    SelectedTextSource,
    accessibility_trusted,
    request_accessibility_prompt,
)
from ai_translate.interfaces.cli import CliServices, run
from ai_translate.interfaces.input_box import InputTranslatePresenter
from ai_translate.interfaces.listen import DesktopListener
from ai_translate.interfaces.live_overlay import LiveOverlayPresenter
from ai_translate.interfaces.menubar import cocoa_app_loop, run_status_app
from ai_translate.interfaces.overlay import OverlayPresenter
from ai_translate.interfaces.region_picker import RegionPicker
from ai_translate.interfaces.settings import SettingsPresenter


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
    start_listener = None
    start_app = None
    if "listen" in args or "app" in args:
        live_ui = LiveOverlayPresenter()
        listener = DesktopListener(
            selection=selection_service(settings),
            ocr_translate=ocr_translate_service(settings),
            read_selected_text=SelectedTextSource().read_selected_text,
            capture_region=RegionScreenshot().capture_region,
            presenter=OverlayPresenter(),
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
        live_ui.set_stop(listener.stop_live)
        if "app" in args:
            def save_preferences(prefs: AppPreferences) -> None:
                upsert_env_values(resolve_env_path(), prefs.to_env())
                refreshed = Settings.load()
                listener.replace_runtime(
                    selection=selection_service(refreshed),
                    ocr_translate=ocr_translate_service(refreshed),
                    source_lang=refreshed.translate.source_lang,
                    target_lang=refreshed.translate.target_lang,
                    selection_hotkey=refreshed.hotkey.selection,
                    ocr_hotkey=refreshed.hotkey.ocr,
                    live_hotkey=refreshed.hotkey.live_ocr,
                )

            settings_ui = SettingsPresenter(
                load=lambda: Settings.load().preferences(),
                save=save_preferences,
            )
            input_ui = InputTranslatePresenter(translate=listener.handle_typed_text)

            def start_app_run() -> int:
                return run_status_app(
                    listener,
                    open_settings=settings_ui.show,
                    open_input=input_ui.show,
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


if __name__ == "__main__":
    raise SystemExit(main())
