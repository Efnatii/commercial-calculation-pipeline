from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import as_list
from wrapper_modules.rag_anything.core.env import is_placeholder
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP

def check_storage_backends(checker: Any, env: dict[str, str]) -> None:
    declared = [str(item) for item in as_list(checker.storage_backends.get("declared", []))]
    if declared:
        checker.add("storage", "declared_backends", STATUS_OK, ", ".join(declared))
    selector_values = [
        str(env.get(key, ""))
        for key in (
            "LIGHTRAG_KV_STORAGE",
            "LIGHTRAG_VECTOR_STORAGE",
            "LIGHTRAG_DOC_STATUS_STORAGE",
            "LIGHTRAG_GRAPH_STORAGE",
        )
    ]
    for name in declared:
        backend = checker.storage_backends.get(name, {})
        if not isinstance(backend, dict):
            continue
        required_keys = [str(item) for item in as_list(backend.get("required_keys", []))]
        selector_tokens = [str(item) for item in as_list(backend.get("selector_contains", []))]
        selected = any(
            token and token.lower() in value.lower()
            for token in selector_tokens
            for value in selector_values
        )
        configured = any(key in env and str(env.get(key, "")).strip() for key in required_keys)
        if not selected and not configured:
            checker.add("storage", name, STATUS_SKIP, "Not selected/configured")
            continue
        missing = [
            key
            for key in required_keys
            if key not in env or is_placeholder(env.get(key), checker.placeholders)
        ]
        checker.add(
            "storage",
            name,
            STATUS_OK if not missing else STATUS_FAIL,
            "Required storage keys are present" if not missing else f"Missing/placeholder keys: {', '.join(missing)}",
            required=selected,
        )

