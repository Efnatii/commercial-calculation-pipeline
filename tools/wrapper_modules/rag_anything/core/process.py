from __future__ import annotations
import os
import re
import subprocess
import sys
import time
from pathlib import Path
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
def run_command(
    command: list[str], timeout_seconds: int, cwd: Path | None = None
) -> tuple[bool, str, int | None]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False, f"Command not found: {command[0]}", None
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout_seconds}s: {' '.join(command)}", None
    except Exception as exc:  # pragma: no cover - defensive reporting
        return False, f"Command failed to start: {exc}", None
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        return True, output, result.returncode
    return False, output or f"Exit code {result.returncode}", result.returncode
def compact_error_output(text: str) -> str:
    clean = ANSI_RE.sub("", text or "")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        if "Error" in line or "Exception" in line or "No module named" in line:
            return line
    return lines[-1]
def run_first_success(
    commands: list[list[str]], timeout_seconds: int
) -> tuple[bool, str, list[str] | None]:
    messages: list[str] = []
    for command in commands:
        ok, output, _ = run_command(command, timeout_seconds)
        if ok:
            return True, output, command
        messages.append(f"{' '.join(command)} -> {output}")
    return False, "; ".join(messages), None
def python_import_check(
    python: str,
    import_statement: str,
    timeout_seconds: int,
    extra_pythonpath: Path | None = None,
) -> tuple[bool, str]:
    code = (
        "import importlib\n"
        f"{import_statement}\n"
        "print('ok')\n"
    )
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["PYTHON_COLORS"] = "0"
    env["TERM"] = "dumb"
    if extra_pythonpath is not None:
        old = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(extra_pythonpath) + (os.pathsep + old if old else "")
    try:
        result = subprocess.run(
            [python, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False, f"Python executable not found: {python}"
    except subprocess.TimeoutExpired:
        return False, f"Python import check timed out after {timeout_seconds}s"
    if result.returncode == 0:
        return True, (result.stdout or "").strip()
    return False, compact_error_output((result.stderr or result.stdout) or "")
__all__ = [
    "run_command",
    "compact_error_output",
    "run_first_success",
    "python_import_check",
]
