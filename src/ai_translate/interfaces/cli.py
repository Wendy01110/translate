from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ai_translate import __version__
from ai_translate.core.errors import ImageSourceError, SelectionReadError
from ai_translate.core.models import ConfigStatus, JobStatus
from ai_translate.core.ports import OcrEngine
from ai_translate.features.ocr_translate import OcrTranslateService
from ai_translate.features.selection import SelectionTranslateService


@dataclass(frozen=True)
class CliServices:
    ocr: OcrEngine | None = None
    ocr_translate: OcrTranslateService | None = None
    selection: SelectionTranslateService | None = None
    load_image: Callable[[str], tuple[bytes, str]] | None = None
    capture_region: Callable[[], tuple[bytes, str]] | None = None
    read_selected_text: Callable[[], str] | None = None
    start_listener: Callable[[], int] | None = None
    start_app: Callable[[], int] | None = None
    source_lang: str = "auto"
    target_lang: str = "zh"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-translate",
        description="Local AI translation for selected text and screen OCR.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "config-check",
        help="Show whether the translate and OCR models are configured.",
    )
    text = subparsers.add_parser("text", help="Translate explicit text.")
    text.add_argument("text", nargs="?", default=None, help="Source text.")
    ocr = subparsers.add_parser(
        "ocr",
        help="Recognize text in a local image or a screen region.",
    )
    _add_image_args(ocr)
    ocr_translate = subparsers.add_parser(
        "ocr-translate",
        help="Recognize text, then translate it.",
    )
    _add_image_args(ocr_translate)
    subparsers.add_parser(
        "listen",
        help="Register macOS hotkeys for selection, OCR, and live OCR translation.",
    )
    subparsers.add_parser(
        "app",
        help="Run the macOS menu bar app.",
    )
    return parser


def format_config_status(status: ConfigStatus) -> str:
    translate_key = "set" if status.translate_api_key_set else "unset"
    ocr_key = "set" if status.ocr_api_key_set else "unset"
    return "\n".join(
        [
            "config:",
            f"  env_file: {_display(status.env_file)}",
            "translate:",
            f"  ready: {_flag(status.translate_ready)}",
            f"  provider: {_display(status.translate_provider)}",
            f"  base_url: {_display(status.translate_base_url)}",
            f"  model: {_display(status.translate_model)}",
            f"  api_key: {translate_key}",
            f"  source_lang: {_display(status.translate_source_lang)}",
            f"  target_lang: {_display(status.translate_target_lang)}",
            "ocr:",
            f"  ready: {_flag(status.ocr_ready)}",
            f"  base_url: {_display(status.ocr_base_url)}",
            f"  model: {_display(status.ocr_model)}",
            f"  api_key: {ocr_key}",
            f"  engine: {_display(status.ocr_engine)}",
            f"  vision: {_flag(status.ocr_vision_available)}",
            f"  image_mode: {_display(status.ocr_image_mode)}",
            f"  max_tokens: {status.ocr_max_tokens}",
            "hotkey:",
            f"  selection: {_display(status.hotkey_selection)}",
            f"  ocr: {_display(status.hotkey_ocr)}",
            f"  live_ocr: {_display(status.hotkey_live_ocr)}",
        ]
    )


def run(
    argv: Sequence[str],
    status: ConfigStatus,
    services: CliServices | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv))
    active = services or CliServices()
    if args.command == "config-check":
        print(format_config_status(status))
        return 0
    if args.command == "text":
        return _run_text(args, active)
    if args.command == "ocr":
        return _run_ocr(args, active)
    if args.command == "ocr-translate":
        return _run_ocr_translate(args, active)
    if args.command == "listen":
        if active.start_listener is None:
            print("listen service is not available", file=sys.stderr)
            return 2
        return active.start_listener()
    if args.command == "app":
        if active.start_app is None:
            print("app service is not available", file=sys.stderr)
            return 2
        return active.start_app()
    parser.error(f"unknown command: {args.command}")
    return 2


def _add_image_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", help="One image file. Uses gundam unless OCR_IMAGE_MODE is set.")
    group.add_argument(
        "--pages",
        nargs="+",
        help="Multiple image files in one request. Uses base unless OCR_IMAGE_MODE is set.",
    )
    group.add_argument(
        "--screenshot",
        action="store_true",
        help="Interactively capture a macOS screen region.",
    )


def _run_text(args: argparse.Namespace, services: CliServices) -> int:
    if services.selection is None:
        print("text service is not available", file=sys.stderr)
        return 2
    source = args.text if args.text is not None else ""
    job = services.selection.translate_text(
        source,
        services.source_lang,
        services.target_lang,
    )
    if job.status is not JobStatus.SUCCESS or not job.translated_text:
        print(job.error or "translate_failed", file=sys.stderr)
        return 1
    print(job.translated_text)
    return 0


def _run_ocr(args: argparse.Namespace, services: CliServices) -> int:
    if services.ocr is None:
        print("ocr service is not available", file=sys.stderr)
        return 2
    try:
        pages = _resolve_pages(args, services)
    except (ImageSourceError, SelectionReadError) as exc:
        print(exc.code, file=sys.stderr)
        return 2
    result = services.ocr.recognize_pages(pages)
    if result.status is not JobStatus.SUCCESS or not result.text:
        print(result.error or "ocr_failed", file=sys.stderr)
        return 1
    print(result.text)
    return 0


def _run_ocr_translate(args: argparse.Namespace, services: CliServices) -> int:
    if services.ocr_translate is None:
        print("ocr-translate service is not available", file=sys.stderr)
        return 2
    try:
        pages = _resolve_pages(args, services)
    except (ImageSourceError, SelectionReadError) as exc:
        print(exc.code, file=sys.stderr)
        return 2
    job = services.ocr_translate.translate_pages(
        pages,
        services.source_lang,
        services.target_lang,
    )
    if job.status is JobStatus.FAILURE:
        print(job.error or "ocr_failed", file=sys.stderr)
        return 1
    if job.status is JobStatus.PARTIAL:
        print(job.error or "translate_failed", file=sys.stderr)
        if job.ocr_text:
            print(job.ocr_text)
        return 1
    if job.translated_text:
        print(job.translated_text)
    return 0


def _resolve_pages(
    args: argparse.Namespace,
    services: CliServices,
) -> list[tuple[bytes, str]]:
    if args.screenshot:
        if services.capture_region is None:
            raise ImageSourceError("screenshot_unavailable")
        return [services.capture_region()]
    if services.load_image is None:
        raise ImageSourceError("image_read_failed")
    paths = [args.image] if args.image else list(args.pages)
    return [services.load_image(path) for path in paths]


def _flag(value: bool) -> str:
    return "true" if value else "false"


def _display(value: str) -> str:
    return value if value else "(empty)"
