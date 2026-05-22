from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_SKIP, STATUS_WARN, ToolReport
def report_to_dict(report: ToolReport) -> dict[str, Any]:
    data = asdict(report)
    data["counts"] = report.counts()
    return data
def print_report(report: ToolReport) -> None:
    counts = report.counts()
    print("RAG-Anything external tool check")
    print(f"Project: {report.project_root}")
    print(f"RAG dir: {report.rag_dir}")
    print(f"Config:  {report.config_path}")
    print(f"Counts:  OK={counts.get(STATUS_OK, 0)} WARN={counts.get(STATUS_WARN, 0)} FAIL={counts.get(STATUS_FAIL, 0)} SKIP={counts.get(STATUS_SKIP, 0)}")
    print()
    discovered = report.discovered
    parsers = discovered.get("parsers", {}).get("names", [])
    processors = sorted(discovered.get("processors", {}).keys())
    extras = sorted(discovered.get("pyproject", {}).get("optional_dependencies", {}).keys())
    env_keys = discovered.get("env_surface", {}).get("all_keys", [])
    cli = discovered.get("cli", {})
    exports = discovered.get("exports", {}).get("symbols", [])
    print("Offered by RAG-Anything:")
    print(f"  Parsers:     {', '.join(parsers) if parsers else 'none discovered'}")
    print(f"  Processors:  {', '.join(processors) if processors else 'none discovered'}")
    print(f"  Extras:      {', '.join(extras) if extras else 'none discovered'}")
    print(f"  Env keys:    {len(env_keys)} discovered")
    if cli:
        cli_summary = ", ".join(
            f"{name}:{len(info.get('arguments', []))}" for name, info in sorted(cli.items())
        )
        print(f"  CLI:         {cli_summary}")
    print(f"  Exports:     {len(exports)} discovered")
    print()
    current_category = ""
    for result in report.results:
        if result.category != current_category:
            current_category = result.category
            print(f"[{current_category}]")
        required = " required" if result.required else ""
        print(f"  {result.status:4} {result.name}{required}: {result.detail}")
        if result.remediation and result.status in {STATUS_WARN, STATUS_FAIL}:
            print(f"       fix: {result.remediation}")
    print()
    if report.has_failures():
        print("Result: FAIL")
    elif report.strict and report.has_warnings():
        print("Result: FAIL (strict warnings)")
    elif report.has_warnings():
        print("Result: WARN")
    else:
        print("Result: OK")
def write_report(path: Path, report: ToolReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report_to_dict(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
__all__ = ["report_to_dict", "print_report", "write_report"]
