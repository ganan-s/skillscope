from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from skillscope.application.ingest import IngestSummary
from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    EventType,
    Evidence,
    ReadinessBasis,
    SourceRevision,
)
from skillscope.storage.connection import connect_writable, migrate
from skillscope.storage.repositories import (
    RevisionConflictError,
    SQLiteSnapshotWriter,
)


def snapshot(
    *,
    revision: str,
    hour: int,
    task_ids: tuple[str, ...],
) -> ConversationSnapshot:
    return ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conversation-1",
        source_revision=SourceRevision(
            revision,
            datetime(2026, 9, 19, hour, tzinfo=UTC),
        ),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=tuple(
            CanonicalEvent(
                contract_version=CONTRACT_VERSION,
                event_id=task_id,
                event_type=EventType.TASK_RECORDED,
                harness_id="cursor",
                native_conversation_id="conversation-1",
                sequence=index,
                turn_index=index,
                evidence=Evidence(
                    source_kind="hook",
                    native_event_kind="task_submitted",
                ),
                payload={"raw_text": task_id},
            )
            for index, task_id in enumerate(task_ids)
        ),
    )


def migrated_store(db_path: Path) -> None:
    conn = connect_writable(db_path)
    migrate(conn)
    conn.close()


def test_newer_writer_then_stale_writer_preserves_newer_aggregate(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    migrated_store(db_path)
    older_connection = connect_writable(db_path)
    newer_connection = connect_writable(db_path)
    older = SQLiteSnapshotWriter(older_connection)
    newer = SQLiteSnapshotWriter(newer_connection)

    assert (
        newer.persist(
            snapshot(revision="newer", hour=13, task_ids=("task-1", "task-2"))
        )
        == "inserted"
    )
    assert (
        older.persist(snapshot(revision="older", hour=12, task_ids=("stale-task",)))
        == "skipped_older"
    )

    rows = newer_connection.execute(
        "SELECT event_id FROM events ORDER BY sequence"
    ).fetchall()
    assert [row["event_id"] for row in rows] == ["task-1", "task-2"]
    older_connection.close()
    newer_connection.close()


def test_equal_timestamp_changed_revision_is_a_conflict(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    conn = connect_writable(db_path)
    migrate(conn)
    writer = SQLiteSnapshotWriter(conn)
    writer.persist(snapshot(revision="first", hour=12, task_ids=("task-1",)))

    with pytest.raises(RevisionConflictError):
        writer.persist(snapshot(revision="second", hour=12, task_ids=("task-2",)))

    rows = conn.execute("SELECT event_id FROM events").fetchall()
    assert [row["event_id"] for row in rows] == ["task-1"]
    conn.close()


def test_failed_batch_does_not_replace_last_successful_ingest_time(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    conn = connect_writable(db_path)
    migrate(conn)
    writer = SQLiteSnapshotWriter(conn)
    successful_at = datetime(2026, 9, 19, 12, tzinfo=UTC)
    writer.record_ingest(
        completed_at=successful_at,
        summary=IngestSummary(inserted=1),
    )

    writer.record_ingest(
        completed_at=datetime(2026, 9, 19, 13, tzinfo=UTC),
        summary=IngestSummary(failed=1),
    )

    metadata = dict(conn.execute("SELECT key, value FROM ingest_meta"))
    assert metadata["last_ingest_at"] == successful_at.isoformat()
    assert '"failed": 1' in metadata["last_ingest_summary"]
    conn.close()
