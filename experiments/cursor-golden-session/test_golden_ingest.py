"""Replay a locally generated Cursor golden session through ingest."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from skillscope.application.queries import GetConversation, PageRequest
from skillscope.bootstrap import ingest_cursor
from skillscope.domain.models import (
    DiagnosticCode,
    EligibilityVerdict,
    EventType,
    ReadinessBasis,
    public_conversation_id,
)
from skillscope.plugins.base import ConversationRef, DiscoveryContext
from skillscope.plugins.cursor.plugin import CursorPlugin
from skillscope.storage.readers import SQLiteReadRepository


@pytest.mark.live
def test_discover_when_golden_exists_finds_stable_conversation(
    discovered: tuple[CursorPlugin, ConversationRef],
    expected: dict[str, object],
) -> None:
    _plugin, ref = discovered
    assert ref.native_conversation_id == expected["conversation_id"]
    assert ref.harness_id == "cursor"


@pytest.mark.live
def test_inspect_when_session_ended_is_ready_with_native_end(
    discovered: tuple[CursorPlugin, ConversationRef],
    plugin_context: DiscoveryContext,
    frozen_now: datetime,
) -> None:
    plugin, ref = discovered
    eligibility = plugin.inspect(ref, now=frozen_now, context=plugin_context)
    assert eligibility.verdict == EligibilityVerdict.READY
    assert eligibility.basis == ReadinessBasis.NATIVE_END


@pytest.mark.live
def test_snapshot_when_golden_is_replayed_emits_expected_canonical_events(
    discovered: tuple[CursorPlugin, ConversationRef],
    plugin_context: DiscoveryContext,
    expected: dict[str, object],
) -> None:
    plugin, ref = discovered
    snapshot = plugin.snapshot(ref, context=plugin_context)
    counts = {
        event_type: sum(
            1 for event in snapshot.events if event.event_type == event_type
        )
        for event_type in (
            EventType.TASK_RECORDED,
            EventType.SKILL_ACTIVATED,
            EventType.SESSION_CLOSED,
        )
    }
    expected_types = expected["canonical_event_types"]
    assert counts[EventType.TASK_RECORDED] == expected_types["task.recorded"]
    assert counts[EventType.SKILL_ACTIVATED] == expected_types["skill.activated"]
    assert counts[EventType.SESSION_CLOSED] == expected_types["session.closed"]

    tasks = [
        event
        for event in snapshot.events
        if event.event_type == EventType.TASK_RECORDED
    ]
    activations = [
        event
        for event in snapshot.events
        if event.event_type == EventType.SKILL_ACTIVATED
    ]
    assert tasks[0].payload["raw_text"] == expected["task_text"]
    assert [event.event_id for event in activations] == expected["activation_ids"]
    assert len({event.event_id for event in activations}) == len(activations)
    assert all(event.payload["path"] == expected["skill_path"] for event in activations)

    failed = [
        diagnostic
        for diagnostic in snapshot.diagnostics
        if diagnostic.code == DiagnosticCode.READ_FAILED
    ]
    assert failed, "failed SKILL.md read must remain a diagnostic"
    assert not any(
        event.event_type == EventType.SKILL_ACTIVATED
        and "missing" in str(event.payload.get("path"))
        for event in snapshot.events
    )


@pytest.mark.live
def test_snapshot_when_replayed_does_not_leak_native_cursor_fields(
    discovered: tuple[CursorPlugin, ConversationRef],
    plugin_context: DiscoveryContext,
) -> None:
    plugin, ref = discovered
    raw = json.dumps(plugin.snapshot(ref, context=plugin_context).to_dict())
    for leaked in (
        "user_email",
        "tool_output",
        '"role": "assistant"',
        "hook_event_name",
    ):
        assert leaked not in raw


@pytest.mark.live
def test_ingest_when_golden_is_replayed_persists_queryable_conversation(
    plugin_context: DiscoveryContext,
    expected: dict[str, object],
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "golden.sqlite"
    summary = ingest_cursor(context=plugin_context, db_path=db_path)
    assert summary.failed == 0
    assert summary.inserted >= 1

    detail = GetConversation(SQLiteReadRepository(db_path))(
        public_conversation_id("cursor", str(expected["conversation_id"]))
    )
    assert detail.task_count == expected["canonical_event_types"]["task.recorded"]
    assert (
        detail.activation_count == expected["canonical_event_types"]["skill.activated"]
    )
    assert detail.harness == "cursor"
    page = SQLiteReadRepository(db_path).list_conversations(PageRequest())
    assert any(item.id == detail.id for item in page.items)
