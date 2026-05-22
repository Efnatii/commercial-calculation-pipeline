from __future__ import annotations

from wrapper_platform.modules import ModuleCommand, WrapperModule
from wrapper_modules.rag_anything.commands.check import main as check_main
from wrapper_modules.rag_anything.commands.visual import main as visual_main

MODULE = WrapperModule(
    id="rag-anything",
    title="RAG-Anything external wrapper",
    description=(
        "Checks and visualizes the local HKUDS/RAG-Anything submodule without "
        "registering it as Codex MCP/plugin integration."
    ),
    commands=(
        ModuleCommand("check", "Plain RAG-Anything tool/config check", check_main),
        ModuleCommand("visual", "Visual RAG-Anything console dashboard", visual_main),
    ),
)

__all__ = ["MODULE"]
