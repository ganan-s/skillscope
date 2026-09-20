from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from skillscope.application.ports import IngestMetadata
from skillscope.bootstrap import build_api_app
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
from skillscope.storage.repositories import SQLiteSnapshotWriter

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


def seed_store(db_path: Path) -> ConversationSnapshot:
    snapshot = ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conversation-no-skills",
        source_revision=SourceRevision("revision-1", NOW),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=(
            CanonicalEvent(
                contract_version=CONTRACT_VERSION,
                event_id="task-1",
                event_type=EventType.TASK_RECORDED,
                harness_id="cursor",
                native_conversation_id="conversation-no-skills",
                sequence=1,
                turn_index=0,
                evidence=Evidence(
                    source_kind="hook",
                    native_event_kind="beforeSubmitPrompt",
                ),
                occurred_at=NOW,
                time_provenance=TimeProvenance.COLLECTOR_OBSERVED,
                payload={"raw_text": "Explain the repository."},
            ),
        ),
        title=None,
    )
    conn = connect_writable(db_path)
    migrate(conn)
    writer = SQLiteSnapshotWriter(conn)
    writer.persist(snapshot)
    writer.record_ingest(
        completed_at=NOW,
        summary=IngestMetadata(1, 0, 0, 0, 0),
    )
    conn.close()
    return snapshot


def _empty_snapshot(
    conversation_id: str,
    *,
    started_at: datetime | None,
    ended_at: datetime | None,
) -> ConversationSnapshot:
    return ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id=conversation_id,
        source_revision=SourceRevision(f"revision-{conversation_id}", NOW),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=(),
        started_at=started_at,
        ended_at=ended_at,
    )


def test_api_when_store_contains_no_skills_exposes_meta_list_and_detail(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    snapshot = seed_store(db_path)
    client = TestClient(build_api_app(db_path))

    metadata = client.get("/api/v1/meta")
    listing = client.get("/api/v1/conversations")
    detail = client.get(f"/api/v1/conversations/{snapshot.public_id}")

    assert metadata.status_code == 200
    assert metadata.json()["harnesses"] == ["cursor"]
    assert metadata.json()["last_ingest_summary"]["inserted"] == 1
    assert listing.status_code == 200
    assert listing.json()["items"][0]["skills"] == []
    assert listing.json()["items"][0]["task_count"] == 1
    assert listing.json()["items"][0]["load_failure_count"] == 0
    assert detail.status_code == 200
    assert detail.json()["tasks"][0]["text"] == "Explain the repository."
    assert detail.json()["skill_activations"] == []
    assert detail.json()["skill_load_failures"] == []


def test_api_reads_legacy_row_without_persisted_public_id(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    snapshot = seed_store(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE conversations SET public_id = NULL")
    conn.commit()
    conn.close()
    client = TestClient(build_api_app(db_path))

    listing = client.get("/api/v1/conversations")
    detail = client.get(f"/api/v1/conversations/{snapshot.public_id}")

    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == snapshot.public_id
    assert detail.status_code == 200


def test_api_when_conversation_is_unknown_returns_stable_error(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    seed_store(db_path)
    client = TestClient(build_api_app(db_path))

    response = client.get("/api/v1/conversations/conv_missing")

    assert response.status_code == 404
    assert response.json() == {
        "code": "conversation_not_found",
        "message": "Conversation not found.",
        "details": None,
    }


def test_api_when_limit_is_invalid_returns_contract_error(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    seed_store(db_path)
    client = TestClient(build_api_app(db_path))

    response = client.get("/api/v1/conversations?limit=101")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_pagination"


def test_api_when_cursor_is_unknown_returns_contract_error(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    seed_store(db_path)
    client = TestClient(build_api_app(db_path))

    response = client.get("/api/v1/conversations?cursor=dW5rbm93bg")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_pagination"


def test_api_paginates_in_stable_newest_first_order(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    conn = connect_writable(db_path)
    migrate(conn)
    writer = SQLiteSnapshotWriter(conn)
    snapshots = (
        _empty_snapshot(
            "newest",
            started_at=datetime(2026, 9, 19, 13, tzinfo=UTC),
            ended_at=datetime(2026, 9, 19, 14, tzinfo=UTC),
        ),
        _empty_snapshot(
            "older",
            started_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
            ended_at=datetime(2026, 9, 19, 13, tzinfo=UTC),
        ),
        _empty_snapshot(
            "missing-end",
            started_at=datetime(2026, 9, 19, 15, tzinfo=UTC),
            ended_at=None,
        ),
    )
    for snapshot in reversed(snapshots):
        writer.persist(snapshot)
    conn.close()
    client = TestClient(build_api_app(db_path))

    first = client.get("/api/v1/conversations?limit=1").json()
    second = client.get(
        "/api/v1/conversations",
        params={"limit": 1, "cursor": first["next_cursor"]},
    ).json()
    third = client.get(
        "/api/v1/conversations",
        params={"limit": 1, "cursor": second["next_cursor"]},
    ).json()

    page_ids = [
        first["items"][0]["id"],
        second["items"][0]["id"],
        third["items"][0]["id"],
    ]
    assert page_ids == [snapshot.public_id for snapshot in snapshots]
    assert first["next_cursor"] is not None
    assert second["next_cursor"] is not None
    assert third["next_cursor"] is None


def test_api_when_store_is_missing_returns_store_missing(tmp_path: Path) -> None:
    client = TestClient(build_api_app(tmp_path / "missing.sqlite"))

    response = client.get("/api/v1/meta")

    assert response.status_code == 503
    assert response.json()["code"] == "store_missing"


def test_api_when_store_schema_is_newer_returns_store_incompatible(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "future.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE schema_meta (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_meta VALUES (999)")
    conn.commit()
    conn.close()

    response = TestClient(build_api_app(db_path)).get("/api/v1/meta")

    assert response.status_code == 503
    assert response.json()["code"] == "store_incompatible"


def test_api_when_store_metadata_is_corrupt_returns_store_unreadable(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    seed_store(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE ingest_meta SET value = 'not-json' WHERE key = 'last_ingest_summary'"
    )
    conn.commit()
    conn.close()

    response = TestClient(build_api_app(db_path)).get("/api/v1/meta")

    assert response.status_code == 503
    assert response.json()["code"] == "store_unreadable"


def test_api_when_conversation_payload_is_corrupt_returns_store_unreadable(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    snapshot = seed_store(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE events SET payload = 'not-json'")
    conn.commit()
    conn.close()
    client = TestClient(build_api_app(db_path))

    listing = client.get("/api/v1/conversations")
    detail = client.get(f"/api/v1/conversations/{snapshot.public_id}")

    assert listing.status_code == 503
    assert listing.json()["code"] == "store_unreadable"
    assert detail.status_code == 503
    assert detail.json()["code"] == "store_unreadable"


def test_list_only_hydrates_events_for_requested_page(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    seed_store(db_path)
    newest = _empty_snapshot(
        "newest",
        started_at=NOW,
        ended_at=NOW,
    )
    conn = connect_writable(db_path)
    SQLiteSnapshotWriter(conn).persist(newest)
    conn.execute(
        "UPDATE events SET payload = 'not-json' "
        "WHERE native_conversation_id = 'conversation-no-skills'"
    )
    conn.commit()
    conn.close()
    client = TestClient(build_api_app(db_path))

    first = client.get("/api/v1/conversations?limit=1")
    second = client.get(
        "/api/v1/conversations",
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
    )

    assert first.status_code == 200
    assert first.json()["items"][0]["id"] == newest.public_id
    assert second.status_code == 503
    assert second.json()["code"] == "store_unreadable"


def test_api_preserves_repeated_activations_and_nested_resource_reads(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    manifest = "---\nname: testing\ndescription: Test guidance\n---\n"
    manifest_payload = {
        "status": "captured",
        "content": manifest,
        "sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "byte_length": len(manifest.encode()),
        "unavailable_reason": None,
    }
    resource = "Use pytest."
    resource_payload = {
        "status": "captured",
        "content": resource,
        "sha256": hashlib.sha256(resource.encode()).hexdigest(),
        "byte_length": len(resource.encode()),
        "unavailable_reason": None,
    }
    common = {
        "contract_version": CONTRACT_VERSION,
        "harness_id": "cursor",
        "native_conversation_id": "conversation-skills",
        "evidence": Evidence(source_kind="hook", native_event_kind="postToolUse"),
        "turn_index": 0,
        "time_provenance": TimeProvenance.COLLECTOR_OBSERVED,
    }
    snapshot = ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conversation-skills",
        source_revision=SourceRevision("revision-1", NOW),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=(
            CanonicalEvent(
                **common,
                event_id="activation-1",
                event_type=EventType.SKILL_ACTIVATED,
                sequence=1,
                payload={
                    "path": "/project/.cursor/skills/testing/SKILL.md",
                    "source_bucket": "project",
                    "name": "testing",
                    "description": "Test guidance",
                    "payload_snapshot": manifest_payload,
                },
            ),
            CanonicalEvent(
                **common,
                event_id="resource-1",
                event_type=EventType.SKILL_RESOURCE_READ,
                sequence=2,
                payload={
                    "parent_activation_id": "activation-1",
                    "path": "/project/.cursor/skills/testing/reference.md",
                    "payload_snapshot": resource_payload,
                },
            ),
            CanonicalEvent(
                **common,
                event_id="activation-2",
                event_type=EventType.SKILL_ACTIVATED,
                sequence=3,
                payload={
                    "path": "/project/.cursor/skills/testing/SKILL.md",
                    "source_bucket": "project",
                    "name": "testing",
                    "description": "Test guidance",
                    "payload_snapshot": manifest_payload,
                },
            ),
        ),
    )
    conn = connect_writable(db_path)
    migrate(conn)
    writer = SQLiteSnapshotWriter(conn)
    writer.persist(snapshot)
    writer.record_ingest(
        completed_at=NOW,
        summary=IngestMetadata(1, 0, 0, 0, 0),
    )
    conn.close()

    response = TestClient(build_api_app(db_path)).get(
        f"/api/v1/conversations/{snapshot.public_id}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skills"][0]["activation_count"] == 2
    assert [item["id"] for item in body["skill_activations"]] == [
        "activation-1",
        "activation-2",
    ]
    assert body["skill_activations"][0]["resource_reads"][0]["id"] == "resource-1"
    assert body["skill_activations"][0]["observations"] == {
        "resource_follow_through": True,
        "repeated_in_conversation": True,
        "followed_by_user_task": False,
        "containing_turn_status": "unknown",
    }
    assert body["skill_activations"][1]["observations"]["resource_follow_through"] is (
        False
    )
    assert body["load_failure_count"] == 0
    assert body["skill_load_failures"] == []


def test_api_exposes_failed_loads_and_turn_observations(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    manifest = "---\nname: testing\n---\n"
    manifest_payload = {
        "status": "captured",
        "content": manifest,
        "sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "byte_length": len(manifest.encode()),
        "unavailable_reason": None,
    }
    common = {
        "contract_version": CONTRACT_VERSION,
        "harness_id": "cursor",
        "native_conversation_id": "conversation-effectiveness",
        "time_provenance": TimeProvenance.COLLECTOR_OBSERVED,
        "occurred_at": NOW,
    }
    hook_evidence = Evidence(source_kind="hook", native_event_kind="postToolUse")
    snapshot = ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conversation-effectiveness",
        source_revision=SourceRevision("revision-1", NOW),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=(
            CanonicalEvent(
                **common,
                event_id="task-1",
                event_type=EventType.TASK_RECORDED,
                sequence=1,
                turn_index=0,
                evidence=hook_evidence,
                payload={"raw_text": "Load the testing skill."},
            ),
            CanonicalEvent(
                **common,
                event_id="activation-1",
                event_type=EventType.SKILL_ACTIVATED,
                sequence=2,
                turn_index=0,
                evidence=hook_evidence,
                payload={
                    "path": "/project/.cursor/skills/testing/SKILL.md",
                    "source_bucket": "project",
                    "name": "testing",
                    "payload_snapshot": manifest_payload,
                },
            ),
            CanonicalEvent(
                **common,
                event_id="fail-1",
                event_type=EventType.SKILL_ACTIVATION_FAILED,
                sequence=3,
                turn_index=0,
                evidence=Evidence(
                    source_kind="hook",
                    native_event_kind="read_failed",
                ),
                payload={
                    "path": "/project/.cursor/skills/missing/SKILL.md",
                    "source_bucket": "project",
                    "reason": "failed",
                },
            ),
            CanonicalEvent(
                **common,
                event_id="turn-1",
                event_type=EventType.TURN_COMPLETED,
                sequence=4,
                turn_index=0,
                evidence=Evidence(
                    source_kind="transcript",
                    native_event_kind="turn_ended",
                ),
                payload={"status": "error"},
            ),
            CanonicalEvent(
                **common,
                event_id="task-2",
                event_type=EventType.TASK_RECORDED,
                sequence=5,
                turn_index=1,
                evidence=hook_evidence,
                payload={"raw_text": "Try again."},
            ),
        ),
    )
    conn = connect_writable(db_path)
    migrate(conn)
    writer = SQLiteSnapshotWriter(conn)
    writer.persist(snapshot)
    writer.record_ingest(
        completed_at=NOW,
        summary=IngestMetadata(1, 0, 0, 0, 0),
    )
    conn.close()

    body = (
        TestClient(build_api_app(db_path))
        .get(f"/api/v1/conversations/{snapshot.public_id}")
        .json()
    )

    assert body["load_failure_count"] == 1
    assert body["skill_load_failures"][0]["id"] == "fail-1"
    assert body["skill_load_failures"][0]["reason"] == "failed"
    assert body["skill_activations"][0]["observations"] == {
        "resource_follow_through": False,
        "repeated_in_conversation": False,
        "followed_by_user_task": True,
        "containing_turn_status": "error",
    }
