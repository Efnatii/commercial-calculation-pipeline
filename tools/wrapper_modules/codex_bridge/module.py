from __future__ import annotations

from wrapper_platform.modules import ModuleCommand, WrapperModule
from wrapper_modules.codex_bridge.commands.build_exe import main as build_exe_main
from wrapper_modules.codex_bridge.commands.init import main as init_main
from wrapper_modules.codex_bridge.commands.serve import main as serve_main
from wrapper_modules.codex_bridge.commands.token import main as token_main
from wrapper_modules.codex_bridge.core.tray_app import main as tray_main

MODULE = WrapperModule(
    id="codex-bridge",
    title="Codex LAN bridge",
    description=(
        "Runs a local HTTP bridge and native tray console so LAN clients can "
        "submit isolated Codex CLI jobs to this machine."
    ),
    commands=(
        ModuleCommand("init", "Initialize Codex bridge local config/state", init_main),
        ModuleCommand("serve", "Run Codex bridge HTTP server", serve_main),
        ModuleCommand("tray", "Run native Codex bridge tray console", tray_main),
        ModuleCommand("token", "Manage Codex bridge tokens", token_main),
        ModuleCommand("build-exe", "Build one-file Codex bridge executable", build_exe_main),
    ),
)

__all__ = ["MODULE"]
