from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = PROJECT_ROOT / "docs"
MARKDOWN_ROOTS = [
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "AGENTS.md",
    *DOCS_ROOT.rglob("*.md"),
]
PLAN_STATES = ("in-progress", "pending", "skipped", "completed")
RECENT_COMPLETED_LIMIT = 5
HEADING_RE = re.compile(r"^# .+$", re.MULTILINE)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
PLAN_ITEM_RE = re.compile(r"\[([^\]]+)\]\(\./(in-progress|pending|skipped|completed)/([^)]+\.md)\)")


def test_each_markdown_file_has_exactly_one_top_level_heading() -> None:
    violations: list[str] = []
    for path in _markdown_files():
        text = _without_fenced_blocks(path.read_text(encoding="utf-8"))
        headings = HEADING_RE.findall(text)
        if len(headings) != 1:
            violations.append(f"{path.relative_to(PROJECT_ROOT)}: found {len(headings)} H1 headings")
    assert violations == []


def test_internal_relative_links_exist() -> None:
    missing: list[str] = []
    for path in _markdown_files():
        text = _without_fenced_blocks(path.read_text(encoding="utf-8"))
        for match in LINK_RE.finditer(text):
            target = match.group(2).split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{path.relative_to(PROJECT_ROOT)} -> {target}")
    assert missing == []


def test_each_plan_exists_in_exactly_one_state_directory() -> None:
    names: dict[str, list[str]] = {}
    for state in PLAN_STATES:
        for path in (DOCS_ROOT / "plan" / state).glob("*.md"):
            names.setdefault(path.name, []).append(state)
    duplicates = {
        name: states for name, states in names.items() if len(states) > 1
    }
    assert duplicates == {}


def test_plan_index_lists_all_active_and_skipped_plans() -> None:
    index = (DOCS_ROOT / "plan" / "README.md").read_text(encoding="utf-8")
    listed = {(state, name) for _, state, name in PLAN_ITEM_RE.findall(index)}
    expected: set[tuple[str, str]] = set()
    for state in ("in-progress", "pending", "skipped"):
        for path in (DOCS_ROOT / "plan" / state).glob("*.md"):
            expected.add((state, path.name))
    assert listed >= expected


def test_root_readme_is_user_facing() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "./scripts/install.sh" in readme
    assert (PROJECT_ROOT / "scripts" / "install.sh").is_file()
    assert "AGENTS.md" not in readme
    assert "docs/plan/" not in readme
    assert "pytest" not in readme


def test_recent_completed_section_respects_limit() -> None:
    index = (DOCS_ROOT / "plan" / "README.md").read_text(encoding="utf-8")
    _, _, tail = index.partition("## 最近完成")
    completed_links = re.findall(r"\(\./completed/([^)]+\.md)\)", tail)
    assert len(completed_links) <= RECENT_COMPLETED_LIMIT


def _markdown_files() -> list[Path]:
    files = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "AGENTS.md"]
    files.extend(sorted(DOCS_ROOT.rglob("*.md")))
    return files


def _without_fenced_blocks(text: str) -> str:
    return FENCE_RE.sub("", text)
