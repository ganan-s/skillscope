from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from skillscope.application.ingest import IngestSummary
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
    writer.record_ingest(completed_at=NOW, summary=IngestSummary(inserted=1))
    conn.close()
    return snapshot


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
    assert detail.status_code == 200
    assert detail.json()["tasks"][0]["text"] == "Explain the repository."
    assert detail.json()["skill_activations"] == []


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
    writer.record_ingest(completed_at=NOW, summary=IngestSummary(inserted=1))
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
