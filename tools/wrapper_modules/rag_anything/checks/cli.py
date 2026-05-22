from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import as_list
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_WARN
from wrapper_modules.rag_anything.core.process import run_command

def check_cli_manifest(checker: Any, discovered: dict[str, Any]) -> None:
    for cli_name, manifest in sorted(checker.cli_manifest.items()):
        if not isinstance(manifest, dict):
            continue
        info = discovered.get("cli", {}).get(cli_name, {})
        if not info:
            checker.add("cli", cli_name, STATUS_WARN, "CLI source was not discovered")
            continue
        checker.add(
            "cli",
            cli_name,
            STATUS_OK,
            f"{manifest.get('module', cli_name)} exposes {len(info.get('arguments', []))} argument(s)",
        )
        choices_by_arg = info.get("choices", {})
        for arg_name, discovered_choices in sorted(choices_by_arg.items()):
            manifest_key = arg_name.lstrip("-").replace("-", "_") + "_choices"
            configured_choices = as_list(manifest.get(manifest_key, []))
            if not configured_choices:
                checker.add(
                    "cli",
                    f"{cli_name}:{arg_name}:choices",
                    STATUS_WARN,
                    f"Choices discovered but not declared in config: {', '.join(discovered_choices)}",
                )
                continue
            missing = sorted(set(discovered_choices) - {str(item) for item in configured_choices})
            checker.add(
                "cli",
                f"{cli_name}:{arg_name}:choices",
                STATUS_OK if not missing else STATUS_FAIL,
                "Choices covered" if not missing else f"Missing choices: {', '.join(missing)}",
                required=bool(missing),
            )
        for tool_name in as_list(manifest.get("optional_tools", [])):
            command = checker.commands.get(str(tool_name), [str(tool_name), "--version"])
            ok, output, _ = run_command([str(item) for item in as_list(command)], checker.timeout)
            checker.add(
                "cli",
                f"optional_tool:{tool_name}",
                STATUS_OK if ok else STATUS_WARN,
                output if output else f"{tool_name} command available",
                remediation=f"Install {tool_name} if you need this CLI method.",
            )

