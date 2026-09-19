"""Tests for SQLite snapshot persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    Diagnostic,
    DiagnosticCode,
    EventType,
    Evidence,
    EvidenceQuality,
    ReadinessBasis,
    SourceRevision,
)
from skillscope.storage.connection import (
    SUPPORTED_SCHEMA_VERSION,
    connect_writable,
    migrate,
)
from skillscope.storage.repositories import (
    RevisionConflictError,
    UpsertResult,
    upsert_conversation,
)


def _ts(hour=12):
    return datetime(2026, 9, 19, hour, 0, 0, tzinfo=UTC)


def _make_event(seq=1, event_type=EventType.TASK_RECORDED, event_id=None):
    return CanonicalEvent(
        contract_version=CONTRACT_VERSION,
        event_id=event_id or f"evt-{seq}",
        event_type=event_type,
        harness_id="cursor",
        native_conversation_id="conv-1",
        sequence=seq,
        evidence=Evidence(
            source_kind="hook",
            native_event_kind="postToolUse",
            quality=EvidenceQuality.CONFIRMED,
        ),
        payload={"raw_text": f"task {seq}"},
    )


def _make_snapshot(revision="rev-1", hour=12, events=None, diagnostics=None):
    return ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conv-1",
        source_revision=SourceRevision(revision=revision, updated_at=_ts(hour)),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=tuple(events or [_make_event()]),
        diagnostics=tuple(diagnostics or []),
        title="Test",
        workspace_paths=("/project",),
    )


class TestMigration(unittest.TestCase):
    def test_creates_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            conn = connect_writable(db)
            version = migrate(conn)
            self.assertEqual(version, SUPPORTED_SCHEMA_VERSION)
            conn.close()

    def test_idempotent_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.sqlite"
            conn = connect_writable(db)
            migrate(conn)
            v2 = migrate(conn)
            self.assertEqual(v2, SUPPORTED_SCHEMA_VERSION)
            conn.close()


class TestUpsert(unittest.TestCase):
    def _setup_db(self, tmp):
        db = Path(tmp) / "test.sqlite"
        conn = connect_writable(db)
        migrate(conn)
        return conn

    def test_insert_new_conversation(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            snap = _make_snapshot()
            result = upsert_conversation(conn, snap)
            conn.commit()
            self.assertEqual(result, UpsertResult.INSERTED)

            rows = conn.execute("SELECT * FROM conversations").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["native_conversation_id"], "conv-1")

            events = conn.execute("SELECT * FROM events ORDER BY sequence").fetchall()
            self.assertEqual(len(events), 1)
            conn.close()

    def test_unchanged_on_same_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            snap = _make_snapshot()
            upsert_conversation(conn, snap)
            conn.commit()

            result = upsert_conversation(conn, snap)
            self.assertEqual(result, UpsertResult.UNCHANGED)
            conn.close()

    def test_update_on_newer_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            snap1 = _make_snapshot(revision="rev-1", hour=12, events=[_make_event(1)])
            upsert_conversation(conn, snap1)
            conn.commit()

            snap2 = _make_snapshot(
                revision="rev-2",
                hour=13,
                events=[_make_event(1), _make_event(2)],
            )
            result = upsert_conversation(conn, snap2)
            conn.commit()
            self.assertEqual(result, UpsertResult.UPDATED)

            events = conn.execute("SELECT * FROM events").fetchall()
            self.assertEqual(len(events), 2)
            conn.close()

    def test_skips_older_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            snap_new = _make_snapshot(revision="rev-2", hour=14)
            upsert_conversation(conn, snap_new)
            conn.commit()

            snap_old = _make_snapshot(revision="rev-1", hour=10)
            result = upsert_conversation(conn, snap_old)
            self.assertEqual(result, UpsertResult.SKIPPED_OLDER)

            rows = conn.execute("SELECT source_revision FROM conversations").fetchall()
            self.assertEqual(rows[0]["source_revision"], "rev-2")
            conn.close()

    def test_rejects_changed_revision_with_same_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            upsert_conversation(conn, _make_snapshot(revision="rev-1", hour=12))
            conn.commit()

            with self.assertRaises(RevisionConflictError):
                upsert_conversation(
                    conn,
                    _make_snapshot(revision="rev-2", hour=12),
                )

            conn.close()

    def test_continuation_replaces_children(self):
        """When a conversation is continued, stale child events disappear."""
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            # First ingest: 1 task
            snap1 = _make_snapshot(
                revision="rev-1",
                hour=12,
                events=[_make_event(1, event_id="task-1")],
            )
            upsert_conversation(conn, snap1)
            conn.commit()

            # Continuation: 2 tasks, different revision
            snap2 = _make_snapshot(
                revision="rev-2",
                hour=13,
                events=[
                    _make_event(1, event_id="task-1"),
                    _make_event(2, event_id="task-2"),
                ],
            )
            upsert_conversation(conn, snap2)
            conn.commit()

            events = conn.execute(
                "SELECT event_id FROM events ORDER BY sequence"
            ).fetchall()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event_id"], "task-1")
            self.assertEqual(events[1]["event_id"], "task-2")
            conn.close()

    def test_rollback_on_error(self):
        """A failed conversation does not leave partial data."""
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            snap = _make_snapshot()
            try:
                conn.execute("BEGIN")
                upsert_conversation(conn, snap)
                # Simulate an error before commit
                raise RuntimeError("simulated failure")
            except RuntimeError:
                conn.rollback()

            rows = conn.execute("SELECT * FROM conversations").fetchall()
            self.assertEqual(len(rows), 0)
            conn.close()

    def test_diagnostics_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            diag = Diagnostic(
                code=DiagnosticCode.READ_OUTCOME_UNKNOWN,
                message="test diagnostic",
                path="/s/SKILL.md",
            )
            snap = _make_snapshot(diagnostics=[diag])
            upsert_conversation(conn, snap)
            conn.commit()

            diags = conn.execute("SELECT * FROM diagnostics").fetchall()
            self.assertEqual(len(diags), 1)
            self.assertEqual(diags[0]["code"], "read_outcome_unknown")
            conn.close()

    def test_event_payload_is_canonical_json(self):
        """Events stored contain canonical JSON, not Cursor-native shapes."""
        with tempfile.TemporaryDirectory() as tmp:
            conn = self._setup_db(tmp)
            snap = _make_snapshot()
            upsert_conversation(conn, snap)
            conn.commit()

            row = conn.execute("SELECT payload FROM events").fetchone()
            payload = json.loads(row["payload"])
            self.assertIn("raw_text", payload)
            # No Cursor-native fields
            self.assertNotIn("user_email", payload)
            self.assertNotIn("tool_output", payload)
            conn.close()


if __name__ == "__main__":
    unittest.main()
