from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skillscope.application.queries import GetConversation, PageRequest
from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    EventType,
    Evidence,
    ReadinessBasis,
    SourceRevision,
    TimeProvenance,
)
from skillscope.storage.connection import connect_writable, migrate
from skillscope.storage.readers import SQLiteReadRepository
from skillscope.storage.repositories import SQLiteSnapshotWriter

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


def test_persist_when_snapshot_includes_effectiveness_events_projects_them(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    snapshot = ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conversation-effectiveness",
        source_revision=SourceRevision("revision-1", NOW),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=(
            CanonicalEvent(
                contract_version=CONTRACT_VERSION,
                event_id="task-1",
                event_type=EventType.TASK_RECORDED,
                harness_id="cursor",
                native_conversation_id="conversation-effectiveness",
                sequence=1,
                turn_index=0,
                evidence=Evidence(
                    source_kind="hook",
                    native_event_kind="task_submitted",
                ),
                occurred_at=NOW,
                time_provenance=TimeProvenance.COLLECTOR_OBSERVED,
                payload={"raw_text": "Load the skill."},
            ),
            CanonicalEvent(
                contract_version=CONTRACT_VERSION,
                event_id="fail-1",
                event_type=EventType.SKILL_ACTIVATION_FAILED,
                harness_id="cursor",
                native_conversation_id="conversation-effectiveness",
                sequence=2,
                turn_index=0,
                evidence=Evidence(source_kind="hook", native_event_kind="read_failed"),
                occurred_at=NOW,
                time_provenance=TimeProvenance.COLLECTOR_OBSERVED,
                payload={
                    "path": "/project/.cursor/skills/missing/SKILL.md",
                    "source_bucket": "project",
                    "reason": "timeout",
                },
            ),
            CanonicalEvent(
                contract_version=CONTRACT_VERSION,
                event_id="turn-1",
                event_type=EventType.TURN_COMPLETED,
                harness_id="cursor",
                native_conversation_id="conversation-effectiveness",
                sequence=3,
                turn_index=0,
                evidence=Evidence(
                    source_kind="transcript",
                    native_event_kind="turn_ended",
                ),
                payload={"status": "error"},
            ),
        ),
    )
    conn = connect_writable(db_path)
    migrate(conn)
    SQLiteSnapshotWriter(conn).persist(snapshot)
    conn.close()

    stored = connect_writable(db_path)
    types = [
        row["event_type"]
        for row in stored.execute(
            "SELECT event_type FROM events ORDER BY sequence"
        ).fetchall()
    ]
    stored.close()
    assert types == [
        "task.recorded",
        "skill.activation_failed",
        "turn.completed",
    ]

    detail = GetConversation(SQLiteReadRepository(db_path))(snapshot.public_id)
    listing = SQLiteReadRepository(db_path).list_conversations(PageRequest())

    assert listing.items[0].load_failure_count == 1
    assert detail.skill_load_failures[0].id == "fail-1"
    assert detail.skill_load_failures[0].reason == "timeout"
    assert detail.skill_activations == ()
