from __future__ import annotations

import sys
from collections.abc import Sequence

from ai_translate.bootstrap.composition import config_status
from ai_translate.config import Settings
from ai_translate.interfaces.cli import run


def main(argv: Sequence[str] | None = None) -> int:
    status = config_status(Settings.load())
    return run(sys.argv[1:] if argv is None else argv, status)


if __name__ == "__main__":
    raise SystemExit(main())
