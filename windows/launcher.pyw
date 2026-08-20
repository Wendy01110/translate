from __future__ import annotations

import os
from pathlib import Path

from ai_translate.app import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("AI_TRANSLATE_PROJECT_ROOT", str(PROJECT_ROOT))
os.environ.setdefault("AI_TRANSLATE_HOST_NAME", "AI Translate")

raise SystemExit(main(["app"]))
