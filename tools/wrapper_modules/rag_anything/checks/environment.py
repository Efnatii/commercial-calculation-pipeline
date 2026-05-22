from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from wrapper_modules.rag_anything.core.config import as_list, parse_bool
from wrapper_modules.rag_anything.core.env import is_placeholder, load_effective_env, redact_value
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN
from wrapper_modules.rag_anything.core.paths import resolve_path
from wrapper_modules.rag_anything.core.validation import has_valid_url

def check_env_files(checker: Any) -> tuple[dict[str, str], dict[str, Any]]:
    env_paths = [
        resolve_path(checker.project_root, str(item))
        for item in as_list(checker.paths.get("env_files", []))
    ]
    effective_env, loaded, missing = load_effective_env(
        env_paths,
        bool(checker.execution.get("include_process_env", True)),
    )
    if loaded:
        checker.add("config", "env_files", STATUS_OK, f"Loaded {', '.join(loaded)}")
    else:
        checker.add(
            "config",
            "env_files",
            STATUS_WARN,
            "No configured .env files were found; process environment and RAG defaults will be used",
        )
    for missing_path in missing:
        checker.add("config", "env_file_missing", STATUS_SKIP, missing_path)
    configured_env = checker.configured_env_keys()
    redacted = {
        key: redact_value(key, value, checker.secret_env)
        for key, value in sorted(effective_env.items())
        if key in configured_env
    }
    env_report = {"loaded_files": loaded, "missing_files": missing, "effective_subset": redacted}
    return effective_env, env_report


def check_env_values(checker: Any, env: dict[str, str]) -> None:
    for key in sorted(checker.required_env):
        value = env.get(key)
        if value is None or value == "":
            checker.add(
                "config",
                f"env:{key}",
                STATUS_FAIL,
                "Required env var is not set",
                required=True,
                remediation=f"Set {key} in .env or remove it from policy.required_env.",
            )
        elif is_placeholder(value, checker.placeholders):
            checker.add(
                "config",
                f"env:{key}",
                STATUS_FAIL,
                "Required env var still contains a placeholder value",
                required=True,
                remediation=f"Replace placeholder value for {key}.",
            )
        else:
            checker.add("config", f"env:{key}", STATUS_OK, "Set")
    for group_name, group in sorted(checker.env_groups.items()):
        if not isinstance(group, dict):
            continue
        keys = [str(item).strip() for item in as_list(group.get("keys", [])) if str(item).strip()]
        present = [key for key in keys if key in env and env.get(key) not in {None, ""}]
        required = bool(group.get("required", False))
        if required and len(present) < len(keys):
            missing = sorted(set(keys) - set(present))
            checker.add(
                "config",
                f"env_group:{group_name}",
                STATUS_FAIL,
                f"{len(present)}/{len(keys)} keys set; missing {', '.join(missing)}",
                required=True,
            )
        else:
            status = STATUS_OK if present else STATUS_SKIP
            detail = f"{len(present)}/{len(keys)} keys set"
            if group.get("description"):
                detail = f"{detail} - {group.get('description')}"
            checker.add("config", f"env_group:{group_name}", status, detail)
    parser = env.get("PARSER", "mineru").strip().lower()
    if parser not in {"mineru", "docling", "paddleocr"}:
        checker.add(
            "config",
            "PARSER",
            STATUS_FAIL,
            f"Unsupported parser '{parser}'",
            required=True,
            remediation="Use one of: mineru, docling, paddleocr.",
        )
    else:
        checker.add("config", "PARSER", STATUS_OK, parser)
    method = env.get("PARSE_METHOD", "auto").strip().lower()
    if method not in {"auto", "ocr", "txt"}:
        checker.add(
            "config",
            "PARSE_METHOD",
            STATUS_FAIL,
            f"Unsupported parse method '{method}'",
            required=True,
            remediation="Use one of: auto, ocr, txt.",
        )
    else:
        checker.add("config", "PARSE_METHOD", STATUS_OK, method)
    enum_config = checker.env_validation.get("enums", {})
    for key, choices in sorted(enum_config.items()):
        if key not in env:
            continue
        allowed = {str(item) for item in as_list(choices)}
        value = str(env[key]).strip()
        if value not in allowed and value.lower() not in {item.lower() for item in allowed}:
            checker.add("config", key, STATUS_FAIL, f"Expected one of {sorted(allowed)}, got '{value}'")
        else:
            checker.add("config", key, STATUS_OK, value)
    for key in sorted(str(item) for item in as_list(checker.env_validation.get("booleans", []))):
        if key not in env:
            continue
        normalized = str(env[key]).strip().lower()
        if normalized not in {"1", "0", "true", "false", "yes", "no", "y", "n", "on", "off"}:
            checker.add("config", key, STATUS_FAIL, f"Expected boolean, got '{env[key]}'")
    for key in sorted(str(item) for item in as_list(checker.env_validation.get("urls", []))):
        if key not in env or not str(env[key]).strip():
            continue
        value = str(env[key]).strip()
        parsed = urlparse(value)
        if key == "REDIS_URI":
            valid = parsed.scheme in {"redis", "rediss"} and bool(parsed.netloc)
        elif key == "NEO4J_URI":
            valid = parsed.scheme in {"neo4j", "neo4j+s", "bolt", "bolt+s"} and bool(parsed.netloc)
        elif key == "MILVUS_URI":
            valid = (parsed.scheme in {"http", "https", "tcp"} and bool(parsed.netloc)) or value.startswith("./")
        else:
            valid = has_valid_url(value)
        checker.add("config", key, STATUS_OK if valid else STATUS_WARN, "URL syntax looks valid" if valid else f"Unexpected URL/URI: {value}")
    for key in sorted(str(item) for item in as_list(checker.env_validation.get("comma_lists", []))):
        if key not in env:
            continue
        values = [item.strip() for item in str(env[key]).split(",") if item.strip()]
        status = STATUS_OK if values else STATUS_WARN
        checker.add("config", key, status, f"{len(values)} item(s)")
    numeric_minimums = checker.env_validation.get("numeric_minimums", {})
    for key, minimum in numeric_minimums.items():
        if key not in env:
            continue
        try:
            value = int(str(env[key]))
            minimum_value = int(minimum)
        except ValueError:
            checker.add("config", key, STATUS_FAIL, f"Expected integer, got '{env[key]}'")
            continue
        if value < minimum_value:
            checker.add("config", key, STATUS_FAIL, f"Expected >= {minimum_value}, got {value}")
        else:
            checker.add("config", key, STATUS_OK, str(value))
    numeric_ranges = checker.env_validation.get("numeric_ranges", {})
    for key, bounds in numeric_ranges.items():
        if key not in env:
            continue
        values = as_list(bounds)
        if len(values) != 2:
            continue
        try:
            value = float(str(env[key]))
            low = float(values[0])
            high = float(values[1])
        except ValueError:
            checker.add("config", key, STATUS_FAIL, f"Expected number, got '{env[key]}'")
            continue
        status = STATUS_OK if low <= value <= high else STATUS_FAIL
        checker.add("config", key, status, f"{value} in range [{low}, {high}]" if status == STATUS_OK else f"Expected [{low}, {high}], got {value}")
    for pair in as_list(checker.env_validation.get("paired", [])):
        items = as_list(pair)
        if len(items) != 2:
            continue
        left, right = str(items[0]), str(items[1])
        has_left = bool(env.get(left))
        has_right = bool(env.get(right))
        if has_left != has_right:
            checker.add(
                "config",
                "public_asset_mapping",
                STATUS_FAIL,
                f"{left} and {right} must be set together",
                required=True,
            )
        elif has_left and has_right:
            checker.add("config", "public_asset_mapping", STATUS_OK, "Configured")

