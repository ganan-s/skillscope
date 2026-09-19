"""Skillscope CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillscope",
        description="Local skill-load visibility for IDE agent conversations",
    )
    sub = parser.add_subparsers(dest="command")

    ingest = sub.add_parser("ingest", help="Discover and ingest closed conversations")
    ingest.add_argument(
        "--harness",
        required=True,
        choices=["cursor"],
        help="Harness plugin to use",
    )
    ingest.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite database path (default: OS-appropriate user data dir)",
    )
    ingest.add_argument(
        "--transcripts",
        type=Path,
        default=None,
        help="Override transcript root directory",
    )
    ingest.add_argument(
        "--spool",
        type=Path,
        default=None,
        help="Override hook spool file path",
    )
    ingest.add_argument(
        "--grace-seconds",
        type=int,
        default=300,
        help="Quiescence grace period in seconds (default: 300)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "ingest":
        return _cmd_ingest(args)

    return 2


def _cmd_ingest(args) -> int:
    from skillscope.application.ingest import run_ingest
    from skillscope.config import default_db_path
    from skillscope.plugins.base import DiscoveryContext
    from skillscope.plugins.cursor.plugin import CursorPlugin

    db_path = args.db or default_db_path()
    plugin = CursorPlugin()

    context = DiscoveryContext(
        home=Path.home(),
        user_data=db_path.parent,
        transcript_override=args.transcripts,
        spool_override=args.spool,
        grace_seconds=args.grace_seconds,
    )

    summary = run_ingest(plugin, context, db_path)
    print(summary)

    if summary.errors:
        for err in summary.errors:
            print(f"  ERROR: {err}", file=sys.stderr)

    return 1 if summary.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
