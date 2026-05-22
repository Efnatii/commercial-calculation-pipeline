from __future__ import annotations
import os
from pathlib import Path
def resolve_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path
def detect_mcp_artifacts(project_root: Path) -> list[str]:
    names = {"mcp.json", ".mcp.json", "mcp.config.json", "plugin.json"}
    found: list[str] = []
    ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)
        dirs[:] = [item for item in dirs if item not in ignored_dirs]
        if ".codex-plugin" in dirs:
            found.append(str(root_path / ".codex-plugin"))
        for filename in files:
            if filename in names:
                found.append(str(root_path / filename))
    return found
def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in (current.parent, *current.parents):
        if (candidate / "configs" / "rag-tool-check.toml").exists() and (candidate / "RAG-Anything").exists():
            return candidate
    return current.parents[3]
__all__ = ["resolve_path", "find_project_root", "detect_mcp_artifacts"]
