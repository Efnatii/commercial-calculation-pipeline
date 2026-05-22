from __future__ import annotations
import json
from pathlib import Path
from typing import Any
DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "rag_dir": "RAG-Anything",
        "env_files": [".env", "RAG-Anything/.env"],
        "report_json": "reports/rag-tool-check.json",
    },
    "execution": {
        "python": "python",
        "include_process_env": True,
        "command_timeout_seconds": 20,
        "network_checks": False,
        "storage_connection_checks": False,
        "sample_ingest_checks": False,
        "smoke_tests": True,
    },
    "policy": {
        "strict": False,
        "required_parsers": ["mineru"],
        "optional_parsers": ["docling", "paddleocr"],
        "required_processors": ["image", "table", "equation"],
        "optional_processors": ["generic"],
        "required_format_features": [],
        "optional_format_features": [
            "office",
            "image",
            "text",
            "markdown",
            "paddleocr_pdf",
        ],
        "selected_parser_required": True,
        "required_env": [
            "LLM_BINDING",
            "LLM_MODEL",
            "LLM_BINDING_HOST",
            "EMBEDDING_BINDING",
            "EMBEDDING_MODEL",
            "EMBEDDING_BINDING_HOST",
        ],
        "secret_env": [
            "OPENAI_API_KEY",
            "LLM_BINDING_API_KEY",
            "EMBEDDING_BINDING_API_KEY",
            "LIGHTRAG_API_KEY",
            "TOKEN_SECRET",
            "POSTGRES_PASSWORD",
            "NEO4J_PASSWORD",
            "MILVUS_TOKEN",
            "QDRANT_API_KEY",
        ],
        "placeholder_values": [
            "",
            "your_api_key",
            "your-secure-api-key-here",
            "your_password",
            "your_username",
            "xxxxxxxx",
            "token-abc123",
        ],
    },
    "providers": {
        "allowed_llm_bindings": [
            "openai",
            "ollama",
            "lollms",
            "azure_openai",
            "lmstudio",
            "vllm",
        ],
        "allowed_embedding_bindings": [
            "openai",
            "ollama",
            "lollms",
            "azure_openai",
            "lmstudio",
            "vllm",
        ],
        "llm_api_key_required_for": ["openai", "azure_openai"],
        "embedding_api_key_required_for": ["openai", "azure_openai"],
    },
    "commands": {
        "mineru": ["mineru", "--version"],
        "libreoffice": [["libreoffice", "--version"], ["soffice", "--version"]],
    },
}
def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
def load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TOML config requires Python 3.11+ or the 'tomli' package. "
            "Alternatively pass a JSON config file."
        ) from exc
    with path.open("rb") as file:
        return tomllib.load(file)
def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    if path.suffix.lower() == ".toml":
        loaded = load_toml(path)
    elif path.suffix.lower() == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")
    return deep_merge(DEFAULT_CONFIG, loaded)
def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if hasattr(value, "__iter__") and not isinstance(value, dict):
        return list(value)
    return [value]
def normalize_names(value: Any) -> set[str]:
    return {str(item).strip().lower() for item in as_list(value) if str(item).strip()}
def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default
from wrapper_modules.rag_anything.core.paths import resolve_path
__all__ = [
    "DEFAULT_CONFIG",
    "deep_merge",
    "load_toml",
    "load_config",
    "as_list",
    "normalize_names",
    "resolve_path",
    "parse_bool",
]
