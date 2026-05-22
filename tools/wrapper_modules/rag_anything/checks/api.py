from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import as_list
from wrapper_modules.rag_anything.core.models import STATUS_OK, STATUS_WARN

def check_exports_and_api(checker: Any, discovered: dict[str, Any]) -> None:
    discovered_exports = set(discovered.get("exports", {}).get("symbols", []))
    for group_name, group in sorted(checker.exports_manifest.items()):
        if not isinstance(group, dict):
            continue
        symbols = {str(item) for item in as_list(group.get("symbols", []))}
        required = bool(group.get("required", False))
        missing = sorted(symbols - discovered_exports)
        checker.add(
            "exports",
            group_name,
            checker.required_status(not missing, required),
            "All symbols discovered" if not missing else f"Missing exported symbols: {', '.join(missing)}",
            required=required,
        )
    discovered_methods = {
        method
        for methods in discovered.get("public_api", {}).values()
        for method in methods
    }
    for group_name, group in sorted(checker.api_manifest.items()):
        if not isinstance(group, dict):
            continue
        methods = {str(item) for item in as_list(group.get("methods", []))}
        present = sorted(methods & discovered_methods)
        missing = sorted(methods - discovered_methods)
        status = STATUS_OK if not missing else STATUS_WARN
        checker.add(
            "api",
            group_name,
            status,
            f"{len(present)}/{len(methods)} configured method(s) discovered"
            if not missing
            else f"Missing configured method(s): {', '.join(missing)}",
        )

