from __future__ import annotations

import argparse
from collections.abc import Sequence

from ai_translate import __version__
from ai_translate.core.models import ConfigStatus


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
    return parser


def format_config_status(status: ConfigStatus) -> str:
    translate_key = "set" if status.translate_api_key_set else "unset"
    ocr_key = "set" if status.ocr_api_key_set else "unset"
    return "\n".join(
        [
            "translate:",
            f"  ready: {_flag(status.translate_ready)}",
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
        ]
    )


def run(argv: Sequence[str], status: ConfigStatus) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv))
    if args.command == "config-check":
        print(format_config_status(status))
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


def _flag(value: bool) -> str:
    return "true" if value else "false"


def _display(value: str) -> str:
    return value if value else "(empty)"
