from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.models import STATUS_OK, STATUS_WARN
from wrapper_modules.rag_anything.core.process import python_import_check

def check_smoke_manifest(checker: Any) -> None:
    smoke = checker.config.get("smoke_tests", {})
    if not smoke:
        return
    enabled = [name for name, value in smoke.items() if bool(value)]
    disabled = [name for name, value in smoke.items() if not bool(value)]
    checker.add(
        "smoke",
        "manifest",
        STATUS_OK,
        f"enabled={', '.join(enabled) if enabled else 'none'}; disabled={len(disabled)}",
    )
    if smoke.get("import_package_exports", False):
        symbols = sorted(checker.configured_export_symbols())
        import_lines = [
            "import importlib",
            "module = importlib.import_module('raganything')",
            f"symbols = {symbols!r}",
            "missing = [name for name in symbols if not hasattr(module, name)]",
            "assert not missing, missing",
        ]
        ok, output = python_import_check(
            checker.python,
            "\n".join(import_lines),
            checker.timeout,
            checker.rag_dir,
        )
        checker.add(
            "smoke",
            "import_package_exports",
            STATUS_OK if ok else STATUS_WARN,
            "Configured exports import successfully" if ok else output,
            remediation="Install RAG-Anything dependencies before enabling import smoke as a hard gate.",
        )

