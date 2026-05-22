#!/usr/bin/env python3
from __future__ import annotations

import argparse

from wrapper_modules.rag_anything.checks.runner import Checker
from wrapper_modules.rag_anything.console.dashboard import (
    Palette,
    animated_boot,
    configure_text_output,
    interactive_output,
    print_visual_report,
    project_root,
    run_checker_with_spinner,
    should_use_color,
)
from wrapper_modules.rag_anything.core.config import load_config
from wrapper_modules.rag_anything.core.paths import resolve_path
from wrapper_modules.rag_anything.core.reporting import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="?????????? ?????????? ???????? ?????????? RAG-Anything.")
    parser.add_argument(
        "--config",
        default=str(project_root() / "configs" / "rag-tool-check.toml"),
        help="Path to checker TOML/JSON config.",
    )
    parser.add_argument("--python", default=None, help="Python executable used for import checks.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--color", action="store_true", help="Force ANSI colors.")
    parser.add_argument("--plain", action="store_true", help="Force plain output without ANSI colors.")
    parser.add_argument("--no-animations", action="store_true", help="Disable spinner/progress animations.")
    parser.add_argument("--no-json-report", action="store_true", help="Do not write the JSON checker report.")
    parser.add_argument("--details", action="store_true", help="Show full service diagnostics: API, exports, env groups.")
    parser.add_argument("--report-only", action="store_true", help="Always exit 0.")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_text_output()
    args = build_parser().parse_args(argv)
    root = project_root()
    config_path = resolve_path(root, args.config)
    config = load_config(config_path)
    color_enabled = should_use_color(force_color=args.color, plain=args.plain)
    palette = Palette(enabled=color_enabled)
    animations_enabled = interactive_output() and not args.no_animations
    animated_boot(palette, animations_enabled)

    checker = Checker(
        project_root=root,
        config_path=config_path,
        config=config,
        python_override=args.python,
        strict_override=args.strict,
    )
    report = run_checker_with_spinner(checker, palette, animations_enabled)
    print_visual_report(report, palette, details=args.details)

    if not args.no_json_report:
        report_json = config.get("paths", {}).get("report_json")
        if report_json:
            write_report(resolve_path(root, str(report_json)), report)

    if args.report_only:
        return 0
    if report.has_failures() or (report.strict and report.has_warnings()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
