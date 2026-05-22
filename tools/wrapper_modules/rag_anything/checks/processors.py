from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import parse_bool
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_WARN

def check_processors(checker: Any, discovered: dict[str, Any], env: dict[str, str]) -> None:
    processors: dict[str, Any] = discovered.get("processors", {})
    env_flags = {
        "image": ("ENABLE_IMAGE_PROCESSING", True),
        "table": ("ENABLE_TABLE_PROCESSING", True),
        "equation": ("ENABLE_EQUATION_PROCESSING", True),
        "generic": (None, True),
    }
    for name in sorted(set(processors) | checker.required_processors | checker.optional_processors):
        is_required = name in checker.required_processors
        if name not in processors:
            checker.add(
                "processor",
                name,
                STATUS_FAIL if is_required else STATUS_WARN,
                "Processor was expected but not discovered",
                required=is_required,
            )
            continue
        flag, default_enabled = env_flags.get(name, (None, True))
        enabled = default_enabled if flag is None else parse_bool(env.get(flag), default_enabled)
        if not enabled:
            checker.add(
                "processor",
                name,
                STATUS_FAIL if is_required else STATUS_WARN,
                f"Discovered {processors[name].get('class')}, but disabled by {flag}",
                required=is_required,
            )
        else:
            supports = processors[name].get("supports") or []
            detail = processors[name].get("class") or name
            if supports:
                detail = f"{detail}: {', '.join(supports)}"
            checker.add("processor", name, STATUS_OK, detail, required=is_required)
    if parse_bool(env.get("ENABLE_IMAGE_PROCESSING"), True):
        if not env.get("VISION_MODEL") and not env.get("LLM_MODEL"):
            checker.add(
                "processor",
                "image_model_hint",
                STATUS_WARN,
                "Image processing is enabled, but neither VISION_MODEL nor LLM_MODEL is set in checked env",
            )

