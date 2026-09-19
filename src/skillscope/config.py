"""Runtime configuration helpers.

Resolves OS-appropriate default paths for the spool and database.
"""

from __future__ import annotations

import platform
from pathlib import Path


def default_data_dir() -> Path:
    """Return the OS-appropriate user data directory for skillscope."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "skillscope"
    if system == "Linux":
        xdg = Path.home() / ".local" / "share"
        return xdg / "skillscope"
    # Windows fallback (best-effort, not QA'd in v1)
    return Path.home() / ".skillscope"


def default_db_path() -> Path:
    return default_data_dir() / "skillscope.sqlite"


def default_spool_path() -> Path:
    return default_data_dir() / "cursor-hook-spool.jsonl"
