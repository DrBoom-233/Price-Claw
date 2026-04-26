from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def _normalize_host(host: str) -> str:
    normalized = host.strip().lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    return normalized


def domain_from_filename(filename: str) -> str:
    stem = Path(filename).stem.strip().lower()
    sanitized = re.sub(r"[^a-z0-9.-]+", "-", stem).strip("-")
    return sanitized or "unknown"


def extract_domain_from_mhtml(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _ in range(800):
                line = handle.readline()
                if not line:
                    break
                match = _URL_PATTERN.search(line)
                if not match:
                    continue
                parsed = urlparse(match.group(0))
                if parsed.hostname:
                    return _normalize_host(parsed.hostname)
    except Exception:
        return None

    return None
