from __future__ import annotations
import ast
from pathlib import Path
from typing import Any
from wrapper_modules.rag_anything.discovery.ast_helpers import ast_string_list
def discover_exports(rag_dir: Path) -> dict[str, Any]:
    init_py = rag_dir / "raganything" / "__init__.py"
    result: dict[str, Any] = {"symbols": [], "source": str(init_py)}
    if not init_py.exists():
        result["error"] = "file not found"
        return result
    try:
        tree = ast.parse(init_py.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        result["error"] = str(exc)
        return result
    symbols: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    symbols.extend(ast_string_list(node.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "__all__"
                and node.func.attr == "extend"
                and node.args
            ):
                symbols.extend(ast_string_list(node.args[0]))
    result["symbols"] = sorted(set(symbols))
    return result
__all__ = ["discover_exports"]
