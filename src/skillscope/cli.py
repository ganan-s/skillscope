"""Command-line driving adapter for Skillscope."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Skillscope command-line adapter."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
