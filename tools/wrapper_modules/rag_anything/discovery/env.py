from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from wrapper_modules.rag_anything.core.env import parse_env_file
def discover_env_surface(rag_dir: Path) -> dict[str, Any]:
    env_example = rag_dir / "env.example"
    documented: dict[str, dict[str, Any]] = {}
    section = "unsectioned"
    if env_example.exists():
        for line_no, raw_line in enumerate(
            env_example.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            stripped = raw_line.strip()
            if stripped.startswith("###"):
                title = stripped.strip("#").strip()
                if title and not set(title) <= {"-"}:
                    section = title
                continue
            line = stripped
            if line.startswith("#"):
                line = line[1:].strip()
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            match = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=", line)
            if match:
                key = match.group(1)
                documented.setdefault(
                    key, {"sections": [], "lines": [], "source": str(env_example)}
                )
                documented[key]["sections"].append(section)
                documented[key]["lines"].append(line_no)
    code_keys: dict[str, list[str]] = {}
    code_paths = (
        list((rag_dir / "raganything").rglob("*.py"))
        + list((rag_dir / "examples").rglob("*.py"))
        + list((rag_dir / "reproduce").rglob("*.py"))
    )
    patterns = [
        r'get_env_value\("([A-Z0-9_]+)"',
        r'os\.getenv\("([A-Z0-9_]+)"',
        r'os\.environ\.get\("([A-Z0-9_]+)"',
    ]
    for path in code_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            for key in re.findall(pattern, text):
                code_keys.setdefault(key, []).append(str(path))
    return {
        "documented": documented,
        "code": {key: sorted(set(paths)) for key, paths in code_keys.items()},
        "all_keys": sorted(set(documented) | set(code_keys)),
    }
def discover_env_example(rag_dir: Path) -> dict[str, Any]:
    env_example = rag_dir / "env.example"
    values = parse_env_file(env_example, include_commented=True)
    return {
        "path": str(env_example),
        "exists": env_example.exists(),
        "keys": sorted(values),
    }
__all__ = ["discover_env_surface", "discover_env_example"]
