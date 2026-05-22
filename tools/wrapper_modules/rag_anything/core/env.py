from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Any
def strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    output: list[str] = []
    for char in value:
        if escaped:
            output.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            output.append(char)
            continue
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            break
        output.append(char)
    return "".join(output).strip()
def clean_env_value(value: str) -> str:
    value = strip_inline_comment(value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
def parse_env_file(path: Path, include_commented: bool = False) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if not include_commented:
                continue
            line = line[1:].strip()
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        values[key] = clean_env_value(value)
    return values
def load_effective_env(
    env_files: list[Path], include_process_env: bool
) -> tuple[dict[str, str], list[str], list[str]]:
    effective: dict[str, str] = {}
    loaded: list[str] = []
    missing: list[str] = []
    for env_file in env_files:
        if env_file.exists():
            effective.update(parse_env_file(env_file))
            loaded.append(str(env_file))
        else:
            missing.append(str(env_file))
    if include_process_env:
        effective.update({key: str(value) for key, value in os.environ.items()})
    return effective, loaded, missing
def is_secret_key(key: str, secret_keys: set[str]) -> bool:
    upper = key.upper()
    if upper in secret_keys:
        return True
    return any(token in upper for token in ("TOKEN", "PASSWORD", "SECRET", "API_KEY"))
def redact_value(key: str, value: str, secret_keys: set[str]) -> str:
    if not is_secret_key(key, secret_keys):
        return value
    if not value:
        return ""
    return "<redacted>"
def is_placeholder(value: str | None, placeholders: set[str]) -> bool:
    if value is None:
        return True
    normalized = value.strip().strip("'\"").lower()
    if normalized in placeholders:
        return True
    return any(token in normalized for token in ("your_", "xxxxxxxx", "<"))
__all__ = [
    "strip_inline_comment",
    "clean_env_value",
    "parse_env_file",
    "load_effective_env",
    "is_secret_key",
    "redact_value",
    "is_placeholder",
]
