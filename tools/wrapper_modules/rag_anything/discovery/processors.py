from __future__ import annotations
import ast
import re
from pathlib import Path
from typing import Any
def discover_processors(rag_dir: Path) -> dict[str, Any]:
    modal_py = rag_dir / "raganything" / "modalprocessors.py"
    utils_py = rag_dir / "raganything" / "utils.py"
    processors: dict[str, Any] = {}
    if modal_py.exists():
        text = modal_py.read_text(encoding="utf-8", errors="replace")
        for class_name in re.findall(r"^class\s+([A-Za-z]+ModalProcessor)\b", text, re.M):
            name = class_name.replace("ModalProcessor", "").lower()
            if name == "base":
                continue
            processors[name] = {"class": class_name, "supports": []}
    if utils_py.exists():
        try:
            tree = ast.parse(utils_py.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "get_processor_supports":
                    for child in ast.walk(node):
                        if not isinstance(child, ast.Assign):
                            continue
                        if not any(
                            isinstance(target, ast.Name) and target.id == "supports_map"
                            for target in child.targets
                        ):
                            continue
                        if not isinstance(child.value, ast.Dict):
                            continue
                        for key_node, value_node in zip(child.value.keys, child.value.values):
                            if not isinstance(key_node, ast.Constant):
                                continue
                            key = str(key_node.value)
                            supports: list[str] = []
                            if isinstance(value_node, ast.List):
                                for item in value_node.elts:
                                    if isinstance(item, ast.Constant):
                                        supports.append(str(item.value))
                            processors.setdefault(key, {"class": "", "supports": []})
                            processors[key]["supports"] = supports
        except SyntaxError:
            pass
    return processors
__all__ = ["discover_processors"]
