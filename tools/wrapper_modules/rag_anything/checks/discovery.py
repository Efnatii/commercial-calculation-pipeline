from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_WARN

def check_discovery(checker: Any, discovered: dict[str, Any]) -> None:
    parser_info = discovered.get("parsers", {})
    parser_names = parser_info.get("names") or []
    if parser_names:
        checker.add("discover", "parsers", STATUS_OK, ", ".join(parser_names))
    else:
        checker.add(
            "discover",
            "parsers",
            STATUS_FAIL,
            parser_info.get("error") or "No parser names discovered",
            required=True,
        )
    if parser_info.get("custom_registry"):
        checker.add(
            "discover",
            "custom_parser_registry",
            STATUS_OK,
            "RAG-Anything exposes register_parser/unregister_parser APIs",
        )
    processors = discovered.get("processors", {})
    if processors:
        checker.add("discover", "modal_processors", STATUS_OK, ", ".join(sorted(processors)))
    else:
        checker.add("discover", "modal_processors", STATUS_WARN, "No modal processors discovered")
    extras = discovered.get("pyproject", {}).get("optional_dependencies", {})
    if extras:
        checker.add("discover", "optional_extras", STATUS_OK, ", ".join(sorted(extras)))
    else:
        checker.add("discover", "optional_extras", STATUS_WARN, "No optional extras discovered")
    env_example = discovered.get("env_example", {})
    if env_example.get("exists"):
        checker.add(
            "discover",
            "env_example",
            STATUS_OK,
            f"Found {len(env_example.get('keys', []))} documented env keys",
        )
    else:
        checker.add("discover", "env_example", STATUS_WARN, "RAG-Anything/env.example is missing")
    env_surface = discovered.get("env_surface", {})
    env_keys = env_surface.get("all_keys", [])
    if env_keys:
        checker.add("discover", "env_surface", STATUS_OK, f"Found {len(env_keys)} env keys across env.example/code")
    cli = discovered.get("cli", {})
    if cli:
        parts = [
            f"{name}:{len(info.get('arguments', []))}"
            for name, info in sorted(cli.items())
        ]
        checker.add("discover", "cli_surface", STATUS_OK, ", ".join(parts))
    exports = discovered.get("exports", {}).get("symbols", [])
    if exports:
        checker.add("discover", "package_exports", STATUS_OK, ", ".join(exports))

