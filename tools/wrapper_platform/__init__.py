"""Shared wrapper platform for independent tool modules."""

from wrapper_platform.modules import ModuleCommand, WrapperModule
from wrapper_platform.registry import get_command, get_module, list_modules

__all__ = ["ModuleCommand", "WrapperModule", "get_command", "get_module", "list_modules"]
