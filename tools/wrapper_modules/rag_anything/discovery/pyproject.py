from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from wrapper_modules.rag_anything.core.config import load_toml
def discover_pyproject(rag_dir: Path) -> dict[str, Any]:
    pyproject = rag_dir / "pyproject.toml"
    result: dict[str, Any] = {
        "path": str(pyproject),
        "requires_python": "",
        "dependencies": [],
        "optional_dependencies": {},
        "error": "",
    }
    if not pyproject.exists():
        result["error"] = "pyproject.toml not found"
        return result
    try:
        data = load_toml(pyproject)
        project = data.get("project", {})
        result["requires_python"] = str(project.get("requires-python", ""))
        result["dependencies"] = list(project.get("dependencies", []))
        result["optional_dependencies"] = dict(project.get("optional-dependencies", {}))
    except Exception as exc:
        result["error"] = str(exc)
    return result
def parse_min_python(requires_python: str) -> tuple[int, int] | None:
    match = re.search(r">=\s*(\d+)\.(\d+)", requires_python)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))
__all__ = ["discover_pyproject", "parse_min_python"]
