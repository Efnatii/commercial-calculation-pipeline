from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_WARN
from wrapper_modules.rag_anything.core.paths import detect_mcp_artifacts
from wrapper_modules.rag_anything.core.process import run_command
from wrapper_modules.rag_anything.discovery.pyproject import parse_min_python

def check_project(checker: Any, discovered: dict[str, Any]) -> None:
    if checker.rag_dir.exists():
        checker.add("project", "rag_dir", STATUS_OK, f"Found {checker.rag_dir}")
    else:
        checker.add(
            "project",
            "rag_dir",
            STATUS_FAIL,
            f"Missing RAG-Anything directory: {checker.rag_dir}",
            required=True,
            remediation="Initialize submodules: git submodule update --init --recursive",
        )
        return
    ok, output, _ = run_command(["git", "-C", str(checker.rag_dir), "rev-parse", "--short", "HEAD"], checker.timeout)
    if ok:
        checker.add("project", "rag_revision", STATUS_OK, f"RAG-Anything revision {output}")
    else:
        checker.add("project", "rag_revision", STATUS_WARN, output)
    rel = os.path.relpath(checker.rag_dir, checker.project_root).replace("\\", "/")
    ok, output, _ = run_command(["git", "ls-files", "--stage", rel], checker.timeout, checker.project_root)
    if ok and output.startswith("160000 "):
        checker.add("project", "gitlink", STATUS_OK, f"{rel} is tracked as a git submodule")
    elif ok and output:
        checker.add("project", "gitlink", STATUS_WARN, f"{rel} is tracked, but not as gitlink: {output}")
    else:
        checker.add("project", "gitlink", STATUS_WARN, f"{rel} is not tracked as a git submodule")
    pyproject = discovered.get("pyproject", {})
    minimum = parse_min_python(str(pyproject.get("requires_python", "")))
    if minimum:
        current = sys.version_info[:2]
        if current >= minimum:
            checker.add(
                "runtime",
                "python_version",
                STATUS_OK,
                f"Python {current[0]}.{current[1]} satisfies >= {minimum[0]}.{minimum[1]}",
            )
        else:
            checker.add(
                "runtime",
                "python_version",
                STATUS_FAIL,
                f"Python {current[0]}.{current[1]} does not satisfy >= {minimum[0]}.{minimum[1]}",
                required=True,
            )
    mcp_artifacts = detect_mcp_artifacts(checker.project_root)
    if mcp_artifacts:
        checker.add(
            "integration",
            "codex_mcp_plugin_boundary",
            STATUS_WARN,
            "Potential MCP/plugin artifacts found in repository",
            metadata={"paths": mcp_artifacts},
        )
    else:
        checker.add(
            "integration",
            "codex_mcp_plugin_boundary",
            STATUS_OK,
            "No repo-local MCP/plugin registration artifacts found",
        )

