from __future__ import annotations
from urllib.parse import urlparse
def has_valid_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
__all__ = ["has_valid_url"]
