"""Command-line driving adapter for Skillscope."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from skillscope import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the Skillscope command-line parser."""
    parser = argparse.ArgumentParser(
        prog="skillscope",
        description="Inspect skill loads from closed agent conversations.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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
    serve = sub.add_parser("serve", help="Serve the read-only local API")
    serve.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite database path (default: OS-appropriate user data dir)",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Skillscope command-line adapter."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "ingest":
        return _cmd_ingest(args)
    if args.command == "serve":
        return _cmd_serve(args)

    return 2


def _cmd_ingest(args) -> int:
    from skillscope.bootstrap import ingest_cursor
    from skillscope.config import default_db_path
    from skillscope.plugins.base import DiscoveryContext

    db_path = args.db or default_db_path()

    context = DiscoveryContext(
        home=Path.home(),
        user_data=db_path.parent,
        transcript_override=args.transcripts,
        spool_override=args.spool,
        grace_seconds=args.grace_seconds,
    )

    summary = ingest_cursor(context=context, db_path=db_path)
    print(summary)

    if summary.errors:
        for err in summary.errors:
            print(f"  ERROR: {err}", file=sys.stderr)

    return 1 if summary.has_failures else 0


def _cmd_serve(args) -> int:
    import uvicorn

    from skillscope.application.queries import StoreError
    from skillscope.bootstrap import build_api_app, validate_read_store
    from skillscope.config import default_db_path

    db_path = args.db or default_db_path()
    try:
        validate_read_store(db_path)
    except StoreError as exc:
        print(f"Cannot serve snapshot store: {exc.code}", file=sys.stderr)
        return 1
    app = build_api_app(db_path)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
