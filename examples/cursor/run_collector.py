#!/usr/bin/env python3
"""Run the production collector from a source checkout without a venv."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from skillscope.plugins.cursor.collector import main  # noqa: E402

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover - fail open for Cursor
        print(f"skillscope collector failed: {error}", file=sys.stderr)
        print("{}")
        raise SystemExit(1) from error
