from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import as_list
from wrapper_modules.rag_anything.core.models import STATUS_FAIL, STATUS_OK, STATUS_WARN
from wrapper_modules.rag_anything.core.process import python_import_check, run_command

def check_parsers(checker: Any, discovered: dict[str, Any], env: dict[str, str]) -> None:
    parser_names = [str(name).lower() for name in discovered.get("parsers", {}).get("names", [])]
    selected = env.get("PARSER", "mineru").strip().lower()
    required = set(checker.required_parsers)
    if checker.policy.get("selected_parser_required", True):
        required.add(selected)
    for requested in sorted(required):
        if requested not in parser_names:
            checker.add(
                "parser",
                requested,
                STATUS_FAIL,
                "Required parser is not offered by this RAG-Anything revision",
                required=True,
            )
    for parser_name in parser_names:
        is_required = parser_name in required
        if parser_name == "mineru":
            command = as_list(checker.commands.get("mineru", ["mineru", "--version"]))
            ok, output, _ = run_command([str(item) for item in command], checker.timeout)
            checker.add(
                "parser",
                "mineru",
                checker.required_status(ok, is_required),
                output if output else "mineru command is available",
                required=is_required,
                remediation="Install with: pip install -U 'mineru[core]'",
            )
        elif parser_name == "docling":
            ok, output = python_import_check(
                checker.python,
                "from docling.document_converter import DocumentConverter  # noqa",
                checker.timeout,
            )
            checker.add(
                "parser",
                "docling",
                checker.required_status(ok, is_required),
                "docling Python package import works" if ok else output,
                required=is_required,
                remediation="Install with: pip install docling",
            )
        elif parser_name == "paddleocr":
            ok, output = python_import_check(checker.python, "import paddleocr  # noqa", checker.timeout)
            checker.add(
                "parser",
                "paddleocr",
                checker.required_status(ok, is_required),
                "paddleocr import works" if ok else output,
                required=is_required,
                remediation="Install with: pip install -e RAG-Anything[paddleocr], then install paddlepaddle.",
            )
            pdf_required = "paddleocr_pdf" in checker.required_features or is_required
            ok_pdf, output_pdf = python_import_check(checker.python, "import pypdfium2  # noqa", checker.timeout)
            checker.add(
                "parser",
                "paddleocr_pdf_renderer",
                checker.required_status(ok_pdf, pdf_required),
                "pypdfium2 import works" if ok_pdf else output_pdf,
                required=pdf_required,
                remediation="Install with: pip install pypdfium2",
            )
            ok_paddle, output_paddle = python_import_check(checker.python, "import paddle  # noqa", checker.timeout)
            checker.add(
                "parser",
                "paddlepaddle_runtime",
                checker.required_status(ok_paddle, is_required),
                "paddle import works" if ok_paddle else output_paddle,
                required=is_required,
                remediation="Install PaddlePaddle from https://www.paddlepaddle.org.cn/install/quick",
            )

