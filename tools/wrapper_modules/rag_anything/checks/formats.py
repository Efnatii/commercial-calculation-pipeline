from __future__ import annotations

from typing import Any

from wrapper_modules.rag_anything.core.config import as_list
from wrapper_modules.rag_anything.core.models import STATUS_OK, STATUS_WARN
from wrapper_modules.rag_anything.core.process import python_import_check, run_first_success

def configured_extensions(checker: Any, discovered: dict[str, Any], env: dict[str, str]) -> set[str]:
    raw = env.get("SUPPORTED_FILE_EXTENSIONS")
    if raw:
        return {item.strip().lower() for item in raw.split(",") if item.strip()}
    return set(discovered.get("default_extensions") or [])


def check_format_features(checker: Any, discovered: dict[str, Any], env: dict[str, str]) -> None:
    extensions = configured_extensions(checker, discovered, env)
    if extensions:
        checker.add("formats", "supported_extensions", STATUS_OK, ", ".join(sorted(extensions)))
    else:
        checker.add("formats", "supported_extensions", STATUS_WARN, "No supported extensions discovered")
    feature_requirements: dict[str, bool] = {
        name: True for name in checker.required_features
    }
    for name in checker.optional_features:
        feature_requirements.setdefault(name, False)
    extended_image_ext = {".bmp", ".tiff", ".tif", ".gif", ".webp"}
    office_ext = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
    text_ext = {".txt", ".md"}
    if "image" in feature_requirements or extensions & extended_image_ext:
        required = bool(feature_requirements.get("image", False))
        ok, output = python_import_check(checker.python, "import PIL  # noqa", checker.timeout)
        checker.add(
            "formats",
            "image_extra",
            checker.required_status(ok, required),
            "Pillow import works" if ok else output,
            required=required,
            remediation="Install with: pip install 'raganything[image]'",
        )
    if "text" in feature_requirements or extensions & text_ext:
        required = bool(feature_requirements.get("text", False))
        ok, output = python_import_check(checker.python, "import reportlab  # noqa", checker.timeout)
        checker.add(
            "formats",
            "text_extra",
            checker.required_status(ok, required),
            "reportlab import works" if ok else output,
            required=required,
            remediation="Install with: pip install 'raganything[text]'",
        )
    if "office" in feature_requirements or extensions & office_ext:
        required = bool(feature_requirements.get("office", False))
        command_config = checker.commands.get("libreoffice", [["libreoffice", "--version"], ["soffice", "--version"]])
        commands = [[str(part) for part in as_list(command)] for command in as_list(command_config)]
        ok, output, command = run_first_success(commands, checker.timeout)
        detail = output if ok else "LibreOffice/soffice not found"
        if ok and command:
            detail = f"{' '.join(command)} -> {output}"
        checker.add(
            "formats",
            "office_conversion",
            checker.required_status(ok, required),
            detail,
            required=required,
            remediation="Install LibreOffice and ensure libreoffice or soffice is on PATH.",
        )
    if "markdown" in feature_requirements:
        required = bool(feature_requirements.get("markdown", False))
        for module in ("markdown", "weasyprint", "pygments"):
            ok, output = python_import_check(checker.python, f"import {module}  # noqa", checker.timeout)
            checker.add(
                "formats",
                f"markdown_extra:{module}",
                checker.required_status(ok, required),
                f"{module} import works" if ok else output,
                required=required,
                remediation="Install with: pip install 'raganything[markdown]'",
            )

