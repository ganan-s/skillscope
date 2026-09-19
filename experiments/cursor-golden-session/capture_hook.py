#!/usr/bin/env python3
"""Fail-open Cursor hook wrapper that spools into this experiment's .local dir."""

from __future__ import annotations

import os
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
SPOOL_PATH = EXPERIMENT_DIR / ".local" / "raw-spool.jsonl"


def main() -> int:
    os.environ["SKILLSCOPE_SPOOL_PATH"] = str(SPOOL_PATH)
    src = REPO_ROOT / "src"
    if src.is_dir():
        sys.path.insert(0, str(src))
    from skillscope.plugins.cursor.collector import main as collector_main

    return collector_main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover - fail open for Cursor
        print(f"skillscope golden-session capture failed: {error}", file=sys.stderr)
        print("{}")
        raise SystemExit(1) from error
