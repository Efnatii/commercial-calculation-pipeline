from __future__ import annotations
import re
from pathlib import Path
def discover_default_extensions(rag_dir: Path) -> list[str]:
    config_py = rag_dir / "raganything" / "config.py"
    if not config_py.exists():
        return []
    text = config_py.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'"(\.pdf,[^"]+\.md)"', text)
    if not match:
        return []
    return [item.strip().lower() for item in match.group(1).split(",") if item.strip()]
__all__ = ["discover_default_extensions"]
