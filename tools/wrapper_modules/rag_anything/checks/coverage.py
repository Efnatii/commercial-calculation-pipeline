from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import as_list, normalize_names
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP

def check_coverage_manifest(checker: Any, discovered: dict[str, Any]) -> None:
    if not checker.coverage.get("require_full_coverage", False):
        checker.add("coverage", "manifest", STATUS_SKIP, "Full coverage enforcement is disabled")
        return
    parser_names = normalize_names(discovered.get("parsers", {}).get("names", []))
    configured_parsers = checker.required_parsers | checker.optional_parsers
    missing_parsers = sorted(parser_names - configured_parsers)
    checker.add(
        "coverage",
        "parsers",
        STATUS_OK if not missing_parsers else STATUS_FAIL,
        "All discovered parsers are listed" if not missing_parsers else f"Missing parser coverage: {', '.join(missing_parsers)}",
        required=True,
    )
    processor_names = normalize_names(discovered.get("processors", {}).keys())
    configured_processors = checker.required_processors | checker.optional_processors
    missing_processors = sorted(processor_names - configured_processors)
    checker.add(
        "coverage",
        "processors",
        STATUS_OK if not missing_processors else STATUS_FAIL,
        "All discovered processors are listed" if not missing_processors else f"Missing processor coverage: {', '.join(missing_processors)}",
        required=True,
    )
    extras = normalize_names(discovered.get("pyproject", {}).get("optional_dependencies", {}).keys())
    configured_extras = normalize_names(checker.policy.get("required_optional_extras", [])) | normalize_names(
        checker.policy.get("optional_extras", [])
    )
    missing_extras = sorted(extras - configured_extras)
    checker.add(
        "coverage",
        "optional_extras",
        STATUS_OK if not missing_extras else STATUS_FAIL,
        "All optional extras are listed" if not missing_extras else f"Missing optional extra coverage: {', '.join(missing_extras)}",
        required=True,
    )
    if checker.coverage.get("require_full_env_coverage", False):
        discovered_env = set(discovered.get("env_surface", {}).get("all_keys", []))
        configured_env = checker.configured_env_keys()
        missing_env = sorted(discovered_env - configured_env)
        checker.add(
            "coverage",
            "env_keys",
            STATUS_OK if not missing_env else STATUS_FAIL,
            f"All {len(discovered_env)} discovered env keys are grouped"
            if not missing_env
            else f"Missing env key coverage: {', '.join(missing_env)}",
            required=True,
        )
    if checker.coverage.get("require_full_cli_coverage", False):
        for cli_name, info in sorted(discovered.get("cli", {}).items()):
            discovered_args = set(info.get("arguments", []))
            configured_args = set(as_list(checker.cli_manifest.get(cli_name, {}).get("arguments", [])))
            missing_args = sorted(discovered_args - configured_args)
            checker.add(
                "coverage",
                f"cli:{cli_name}",
                STATUS_OK if not missing_args else STATUS_FAIL,
                f"All {len(discovered_args)} CLI args are listed"
                if not missing_args
                else f"Missing CLI arg coverage: {', '.join(missing_args)}",
                required=True,
            )
    if checker.coverage.get("require_full_export_coverage", False):
        discovered_exports = set(discovered.get("exports", {}).get("symbols", []))
        configured_exports = checker.configured_export_symbols()
        missing_exports = sorted(discovered_exports - configured_exports)
        checker.add(
            "coverage",
            "exports",
            STATUS_OK if not missing_exports else STATUS_FAIL,
            "All package exports are listed" if not missing_exports else f"Missing export coverage: {', '.join(missing_exports)}",
            required=True,
        )
    if checker.coverage.get("require_full_api_coverage", False):
        discovered_methods = {
            method
            for methods in discovered.get("public_api", {}).values()
            for method in methods
        }
        configured_methods = checker.configured_api_methods()
        missing_methods = sorted(discovered_methods - configured_methods)
        checker.add(
            "coverage",
            "public_api",
            STATUS_OK if not missing_methods else STATUS_FAIL,
            f"All {len(discovered_methods)} public methods are listed"
            if not missing_methods
            else f"Missing public API coverage: {', '.join(missing_methods)}",
            required=True,
        )

