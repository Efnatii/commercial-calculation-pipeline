from __future__ import annotations
import ast
from pathlib import Path
from typing import Any


def _public_members(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    ignored = {"main"}
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_") and node.name not in ignored:
                names.add(node.name)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            names.add(node.name)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not child.name.startswith("_") and child.name not in ignored:
                        names.add(child.name)
    return sorted(names)


def discover_public_api(rag_dir: Path) -> dict[str, Any]:
    result: dict[str, list[str]] = {}
    package_dir = rag_dir / "raganything"
    for path in sorted(package_dir.rglob("*.py")):
        members = _public_members(path)
        if members:
            result[path.relative_to(package_dir).as_posix()] = members
    return result


__all__ = ["discover_public_api"]
