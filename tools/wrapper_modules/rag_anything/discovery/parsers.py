from __future__ import annotations
import ast
import re
from pathlib import Path
from typing import Any
from wrapper_modules.rag_anything.discovery.ast_helpers import ast_string_tuple
def discover_supported_parsers(rag_dir: Path) -> dict[str, Any]:
    parser_py = rag_dir / "raganything" / "parser.py"
    discovered = {
        "names": [],
        "custom_registry": False,
        "source": str(parser_py),
        "error": "",
    }
    if not parser_py.exists():
        discovered["error"] = "parser.py not found"
        return discovered
    text = parser_py.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "SUPPORTED_PARSERS":
                        discovered["names"] = ast_string_tuple(node.value)
            elif isinstance(node, ast.FunctionDef) and node.name == "register_parser":
                discovered["custom_registry"] = True
    except SyntaxError as exc:
        discovered["error"] = f"Unable to parse parser.py: {exc}"
    if not discovered["names"]:
        matches = re.findall(r'"(mineru|docling|paddleocr)"', text)
        discovered["names"] = sorted(set(matches))
    return discovered
__all__ = ["discover_supported_parsers"]
