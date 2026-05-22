from __future__ import annotations

from wrapper_platform.modules import ModuleCommand, WrapperModule
from wrapper_modules.rag_anything.module import MODULE as RAG_ANYTHING_MODULE

BUILTIN_MODULES: tuple[WrapperModule, ...] = (RAG_ANYTHING_MODULE,)


def list_modules() -> tuple[WrapperModule, ...]:
    return BUILTIN_MODULES


def get_module(module_id: str) -> WrapperModule | None:
    normalized = module_id.strip().lower()
    for module in BUILTIN_MODULES:
        if module.id == normalized:
            return module
    return None


def get_command(module_id: str, command_name: str) -> ModuleCommand | None:
    module = get_module(module_id)
    if module is None:
        return None
    return module.get_command(command_name.strip().lower())


__all__ = ["BUILTIN_MODULES", "list_modules", "get_module", "get_command"]
