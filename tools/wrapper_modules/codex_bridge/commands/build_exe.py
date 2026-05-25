from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from wrapper_modules.codex_bridge.core.config import discover_repo_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the unified Codex bridge executable with PyInstaller.")
    parser.add_argument("--python", default=sys.executable, help="Python executable used for PyInstaller.")
    parser.add_argument("--name", default="codex-bridge", help="Executable base name.")
    parser.add_argument("--dist", default="dist", help="Output directory.")
    parser.add_argument("--venv", default=".codex-bridge/build-venv", help="Local build virtual environment.")
    parser.add_argument("--console", action="store_true", help="Keep a console window for the unified executable.")
    parser.add_argument("--use-current-python", action="store_true", help="Install/use PyInstaller in --python directly.")
    parser.add_argument("--no-install", action="store_true", help="Do not install PyInstaller if missing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = discover_repo_root()
    launcher = root / "tools" / "codex_bridge_app.py"
    static_data = root / "docs" / "codex-ui"
    icon_file = static_data / "assets" / "codex-bridge.ico"
    build_python = Path(args.python)

    if not args.use_current_python:
        venv_dir = (root / args.venv).resolve()
        build_python = venv_dir / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
        if not build_python.exists():
            subprocess.run([args.python, "-m", "venv", str(venv_dir)], check=True)

    if not args.no_install:
        packages = ["pip", "pyinstaller", "pystray", "pillow", "pywebview"]
        subprocess.run([str(build_python), "-m", "pip", "install", "--upgrade", *packages], check=True)

    separator = ";" if sys.platform.startswith("win") else ":"
    command = [
        str(build_python),
        "-m",
        "PyInstaller",
        "--clean",
        "--onefile",
        "--name",
        args.name,
        "--distpath",
        str((root / args.dist).resolve()),
        "--add-data",
        f"{static_data}{separator}docs/codex-ui",
    ]
    if icon_file.exists():
        command.extend(["--icon", str(icon_file)])
    if not args.console:
        command.append("--windowed")
    command.extend(
        [
            "--hidden-import",
            "pystray._win32",
            "--hidden-import",
            "webview.platforms.winforms",
            "--hidden-import",
            "webview.platforms.edgechromium",
        ]
    )
    command.append(str(launcher))
    print(" ".join(command))
    return subprocess.run(command, cwd=str(root), check=False).returncode
