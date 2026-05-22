from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import as_list, normalize_names
from wrapper_modules.rag_anything.core.env import is_placeholder
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_WARN
from wrapper_modules.rag_anything.core.process import run_command
from wrapper_modules.rag_anything.core.validation import has_valid_url

def check_provider_config(checker: Any, env: dict[str, str]) -> None:
    allowed_llm = normalize_names(checker.providers.get("allowed_llm_bindings", []))
    allowed_embedding = normalize_names(checker.providers.get("allowed_embedding_bindings", []))
    llm_key_required = normalize_names(checker.providers.get("llm_api_key_required_for", []))
    embedding_key_required = normalize_names(checker.providers.get("embedding_api_key_required_for", []))
    llm_binding = env.get("LLM_BINDING")
    if llm_binding:
        normalized = llm_binding.strip().lower()
        if normalized not in allowed_llm:
            checker.add("provider", "LLM_BINDING", STATUS_FAIL, f"Unknown LLM binding '{llm_binding}'")
        else:
            checker.add("provider", "LLM_BINDING", STATUS_OK, normalized)
        host = env.get("LLM_BINDING_HOST")
        if host and normalized in {"openai", "azure_openai", "lmstudio", "vllm"} and not has_valid_url(host):
            checker.add("provider", "LLM_BINDING_HOST", STATUS_WARN, f"Host is not an HTTP(S) URL: {host}")
        if normalized in llm_key_required:
            key = env.get("LLM_BINDING_API_KEY") or env.get("OPENAI_API_KEY")
            status = checker.required_status(not is_placeholder(key, checker.placeholders), True)
            checker.add(
                "provider",
                "LLM_API_KEY",
                status,
                "Present" if status == STATUS_OK else f"Missing or placeholder API key for {normalized}",
                required=True,
            )
    embedding_binding = env.get("EMBEDDING_BINDING")
    if embedding_binding:
        normalized = embedding_binding.strip().lower()
        if normalized not in allowed_embedding:
            checker.add("provider", "EMBEDDING_BINDING", STATUS_FAIL, f"Unknown embedding binding '{embedding_binding}'")
        else:
            checker.add("provider", "EMBEDDING_BINDING", STATUS_OK, normalized)
        host = env.get("EMBEDDING_BINDING_HOST")
        if host and normalized in {"openai", "azure_openai", "ollama", "lmstudio", "vllm"} and not has_valid_url(host):
            checker.add("provider", "EMBEDDING_BINDING_HOST", STATUS_WARN, f"Host is not an HTTP(S) URL: {host}")
        if normalized in embedding_key_required:
            key = env.get("EMBEDDING_BINDING_API_KEY") or env.get("OPENAI_API_KEY")
            status = checker.required_status(not is_placeholder(key, checker.placeholders), True)
            checker.add(
                "provider",
                "EMBEDDING_API_KEY",
                status,
                "Present" if status == STATUS_OK else f"Missing or placeholder API key for {normalized}",
                required=True,
            )


def check_provider_tools(checker: Any, env: dict[str, str]) -> None:
    bindings = {
        str(env.get("LLM_BINDING", "")).lower(),
        str(env.get("EMBEDDING_BINDING", "")).lower(),
    }
    if "ollama" in bindings or any(key.startswith("OLLAMA_") for key in env):
        command = [str(item) for item in as_list(checker.commands.get("ollama", ["ollama", "list"]))]
        ok, output, _ = run_command(command, checker.timeout)
        checker.add(
            "provider",
            "ollama_cli",
            STATUS_OK if ok else STATUS_WARN,
            output if output else "ollama CLI is available",
            remediation="Install Ollama and pull the configured embedding/LLM models.",
        )

