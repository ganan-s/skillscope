"""Snapshot persistence: idempotent conversation aggregate replacement."""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import datetime
from enum import Enum

from skillscope.domain.models import CanonicalEvent, ConversationSnapshot, Diagnostic


class UpsertResult:
    INSERTED = "inserted"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED_OLDER = "skipped_older"


def _enum_safe(obj):
    """JSON default handler for enums."""
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _evidence_dict(evt: CanonicalEvent) -> str:
    d = dataclasses.asdict(evt.evidence)
    return json.dumps(d, default=_enum_safe, sort_keys=True)


def upsert_conversation(
    conn: sqlite3.Connection,
    snapshot: ConversationSnapshot,
) -> str:
    """Persist one conversation snapshot idempotently.

    Returns one of UpsertResult constants.
    Raises on unexpected errors (rolls back the transaction).
    """
    rev = snapshot.source_revision.revision
    updated_at = snapshot.source_revision.updated_at.isoformat()
    harness = snapshot.harness_id
    conv_id = snapshot.native_conversation_id

    cursor = conn.execute(
        "SELECT id, source_revision, source_updated_at FROM conversations "
        "WHERE harness_id = ? AND native_conversation_id = ?",
        (harness, conv_id),
    )
    existing = cursor.fetchone()

    if existing:
        row_id = existing["id"]
        old_rev = existing["source_revision"]
        old_updated = existing["source_updated_at"]

        if old_rev == rev:
            return UpsertResult.UNCHANGED

        # Refuse older revision
        if old_updated > updated_at:
            return UpsertResult.SKIPPED_OLDER

        # Replace: delete children, update row
        conn.execute("DELETE FROM events WHERE conversation_id = ?", (row_id,))
        conn.execute("DELETE FROM diagnostics WHERE conversation_id = ?", (row_id,))
        conn.execute(
            "UPDATE conversations SET "
            "contract_version = ?, source_revision = ?, source_updated_at = ?, "
            "readiness_basis = ?, title = ?, workspace_paths = ?, "
            "started_at = ?, ended_at = ? "
            "WHERE id = ?",
            (
                snapshot.contract_version,
                rev,
                updated_at,
                snapshot.readiness_basis.value,
                snapshot.title,
                json.dumps(list(snapshot.workspace_paths)),
                snapshot.started_at.isoformat() if snapshot.started_at else None,
                snapshot.ended_at.isoformat() if snapshot.ended_at else None,
                row_id,
            ),
        )
        _insert_children(conn, row_id, snapshot)
        return UpsertResult.UPDATED
    else:
        cursor = conn.execute(
            "INSERT INTO conversations "
            "(harness_id, native_conversation_id, contract_version, "
            "source_revision, source_updated_at, readiness_basis, "
            "title, workspace_paths, started_at, ended_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                harness,
                conv_id,
                snapshot.contract_version,
                rev,
                updated_at,
                snapshot.readiness_basis.value,
                snapshot.title,
                json.dumps(list(snapshot.workspace_paths)),
                snapshot.started_at.isoformat() if snapshot.started_at else None,
                snapshot.ended_at.isoformat() if snapshot.ended_at else None,
            ),
        )
        row_id = cursor.lastrowid
        _insert_children(conn, row_id, snapshot)
        return UpsertResult.INSERTED


def _insert_children(
    conn: sqlite3.Connection,
    conversation_row_id: int,
    snapshot: ConversationSnapshot,
) -> None:
    for evt in snapshot.events:
        conn.execute(
            "INSERT INTO events "
            "(conversation_id, contract_version, event_id, event_type, "
            "harness_id, native_conversation_id, sequence, native_turn_id, "
            "turn_index, occurred_at, time_provenance, evidence, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                conversation_row_id,
                evt.contract_version,
                evt.event_id,
                evt.event_type.value,
                evt.harness_id,
                evt.native_conversation_id,
                evt.sequence,
                evt.native_turn_id,
                evt.turn_index,
                evt.occurred_at.isoformat() if evt.occurred_at else None,
                evt.time_provenance.value,
                _evidence_dict(evt),
                json.dumps(evt.payload, default=_enum_safe, sort_keys=True),
            ),
        )

    for diag in snapshot.diagnostics:
        conn.execute(
            "INSERT INTO diagnostics "
            "(conversation_id, code, message, path, record_position) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                conversation_row_id,
                diag.code.value,
                diag.message,
                diag.path,
                diag.record_position,
            ),
        )
