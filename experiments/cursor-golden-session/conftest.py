"""Opt-in collection rules for local golden-session replay tests."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skillscope.plugins.base import ConversationRef, DiscoveryContext
from skillscope.plugins.cursor.plugin import CursorPlugin

EXPERIMENT_DIR = Path(__file__).resolve().parent
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))
GOLDEN_DIR = EXPERIMENT_DIR / ".local" / "golden"
HOOKS = GOLDEN_DIR / "hooks.jsonl"
TRANSCRIPTS = GOLDEN_DIR / "transcripts"
EXPECTED = GOLDEN_DIR / "expected.json"
GENERATE_HINT = (
    "Golden session pack is missing. Capture a Cursor conversation, then run "
    "`uv run python experiments/cursor-golden-session/generate_golden.py`."
)


def _live_requested(config: pytest.Config) -> bool:
    if os.environ.get("SKILLSCOPE_LIVE") == "1":
        return True
    markexpr = (getattr(config.option, "markexpr", None) or "").strip()
    if not markexpr:
        return False
    if re.search(r"\bnot\s+live\b", markexpr):
        return False
    return bool(re.search(r"\blive\b", markexpr))


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    live_requested = _live_requested(config)
    golden_ready = HOOKS.is_file() and EXPECTED.is_file()
    for item in items:
        if item.get_closest_marker("live") is None:
            continue
        if not live_requested:
            item.add_marker(
                pytest.mark.skip(
                    reason="live tests require `pytest -m live` or SKILLSCOPE_LIVE=1"
                )
            )
        elif not golden_ready:
            item.add_marker(pytest.mark.skip(reason=GENERATE_HINT))


@pytest.fixture
def expected() -> dict[str, object]:
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


@pytest.fixture
def plugin_context(tmp_path: Path) -> DiscoveryContext:
    return DiscoveryContext(
        home=tmp_path,
        user_data=tmp_path,
        transcript_override=TRANSCRIPTS,
        spool_override=HOOKS,
        grace_seconds=0,
    )


@pytest.fixture
def discovered(
    plugin_context: DiscoveryContext,
) -> tuple[CursorPlugin, ConversationRef]:
    plugin = CursorPlugin()
    refs = list(plugin.discover(plugin_context))
    assert refs, "golden pack produced no conversations"
    return plugin, refs[0]


@pytest.fixture
def frozen_now() -> datetime:
    return datetime(2026, 9, 19, 13, 0, tzinfo=UTC)
