from __future__ import annotations
import ast
from pathlib import Path
from typing import Any
from wrapper_modules.rag_anything.discovery.ast_helpers import ast_string_list, first_argument_name


CLI_KEY_OVERRIDES = {
    "raganything/parser.py": "parser",
    "raganything/batch_parser.py": "batch_parser",
    "raganything/enhanced_markdown.py": "enhanced_markdown",
}


def cli_manifest_key(rag_dir: Path, path: Path) -> str:
    rel = path.relative_to(rag_dir).as_posix()
    if rel in CLI_KEY_OVERRIDES:
        return CLI_KEY_OVERRIDES[rel]
    return rel.removesuffix(".py").replace("/", "_")


def cli_argument_names(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"arguments": [], "choices": {}, "source": str(path)}
    if not path.exists():
        result["error"] = "file not found"
        return result
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        result["error"] = str(exc)
        return result
    arguments: list[str] = []
    choices: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        name = first_argument_name(node)
        if not name:
            continue
        normalized = name.split()[0]
        arguments.append(normalized)
        for keyword in node.keywords:
            if keyword.arg == "choices":
                values = ast_string_list(keyword.value)
                if values:
                    choices[normalized] = values
    result["arguments"] = arguments
    result["choices"] = choices
    return result


def discover_cli(rag_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    roots = [rag_dir / "raganything", rag_dir / "examples", rag_dir / "reproduce"]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            info = cli_argument_names(path)
            if info.get("arguments"):
                key = cli_manifest_key(rag_dir, path)
                info["path"] = path.relative_to(rag_dir).as_posix()
                result[key] = info
    return result


__all__ = ["cli_argument_names", "cli_manifest_key", "discover_cli"]
