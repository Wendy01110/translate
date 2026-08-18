from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_NAME = "ai_translate"
PACKAGE_ROOT = PROJECT_ROOT / "src" / PACKAGE_NAME
TARGET_LAYERS = {
    "core",
    "features",
    "infrastructure",
    "interfaces",
    "bootstrap",
}
ALLOWED_INTERNAL_DEPENDENCIES = {
    "core": set(),
    "features": {"core"},
    "infrastructure": {"core"},
    "interfaces": {"core", "features"},
    "bootstrap": {
        "core",
        "features",
        "infrastructure",
        "interfaces",
    },
}


def test_target_layers_follow_the_internal_import_allowlist() -> None:
    violations: list[str] = []
    for layer in sorted(TARGET_LAYERS):
        layer_root = PACKAGE_ROOT / layer
        if not layer_root.exists():
            continue
        for path in sorted(layer_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for module in _project_imports(tree, path):
                dependency = _top_level_project_module(module)
                if dependency is None or dependency not in TARGET_LAYERS:
                    continue
                if dependency == layer:
                    if layer == "features" and _crosses_feature_boundary(path, module):
                        relative_path = path.relative_to(PROJECT_ROOT)
                        violations.append(
                            f"{relative_path}: feature modules must not import {module}"
                        )
                    continue
                if dependency not in ALLOWED_INTERNAL_DEPENDENCIES[layer]:
                    relative_path = path.relative_to(PROJECT_ROOT)
                    violations.append(
                        f"{relative_path}: {layer} must not import {module}"
                    )

    assert violations == []


def _project_imports(tree: ast.AST, path: Path) -> Iterator[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PACKAGE_NAME or alias.name.startswith(
                    f"{PACKAGE_NAME}."
                ):
                    yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = _resolved_import_from_module(node, path)
            if module is None:
                continue
            if module == PACKAGE_NAME or module.startswith(f"{PACKAGE_NAME}."):
                yield module


def _resolved_import_from_module(
    node: ast.ImportFrom,
    path: Path,
) -> str | None:
    if node.level == 0:
        return node.module

    relative_parts = path.relative_to(PACKAGE_ROOT).with_suffix("").parts
    package_parts = [PACKAGE_NAME, *relative_parts[:-1]]
    parents_to_remove = node.level - 1
    if parents_to_remove > len(package_parts):
        return None
    base_parts = (
        package_parts[: len(package_parts) - parents_to_remove]
        if parents_to_remove
        else package_parts
    )
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _top_level_project_module(module: str) -> str | None:
    parts = module.split(".")
    if not parts or parts[0] != PACKAGE_NAME or len(parts) == 1:
        return None
    return parts[1]


def _crosses_feature_boundary(path: Path, module: str) -> bool:
    current_feature = path.stem
    module_parts = module.split(".")
    if len(module_parts) < 3 or module_parts[1] != "features":
        return False
    imported_feature = module_parts[2]
    return imported_feature != current_feature
