from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from skillscope.bootstrap import build_api_app
from skillscope.domain.models import (
    CONTRACT_VERSION,
    ConversationSnapshot,
    ReadinessBasis,
    SourceRevision,
)
from skillscope.storage.connection import connect_writable, migrate
from skillscope.storage.repositories import SQLiteSnapshotWriter

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_URI = "urn:skillscope:openapi"


def _seed_store(db_path: Path) -> ConversationSnapshot:
    now = datetime(2026, 9, 19, 12, tzinfo=UTC)
    snapshot = ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="contract-conversation",
        source_revision=SourceRevision("revision-1", now),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=(),
    )
    conn = connect_writable(db_path)
    migrate(conn)
    SQLiteSnapshotWriter(conn).persist(snapshot)
    conn.close()
    return snapshot


def _contract() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "docs" / "openapi" / "v1.yaml").read_text())


def _validate(instance: object, schema_name: str) -> None:
    contract = _contract()
    resource = Resource.from_contents(
        contract,
        default_specification=DRAFT202012,
    )
    registry = Registry().with_resource(CONTRACT_URI, resource)
    validator = Draft202012Validator(
        {"$ref": f"{CONTRACT_URI}#/components/schemas/{schema_name}"},
        registry=registry,
        format_checker=FormatChecker(),
    )
    validator.validate(instance)


def test_generated_openapi_exposes_only_documented_api_operations(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    _seed_store(db_path)
    generated = build_api_app(db_path).openapi()
    contract = _contract()

    generated_paths = {
        path: {
            method: set(operation["responses"]) for method, operation in methods.items()
        }
        for path, methods in generated["paths"].items()
        if path.startswith("/api/v1/")
    }
    contract_paths = {
        path: {
            method: set(operation["responses"]) for method, operation in methods.items()
        }
        for path, methods in contract["paths"].items()
    }

    assert generated_paths == contract_paths


def test_api_responses_validate_against_checked_in_openapi(tmp_path: Path) -> None:
    db_path = tmp_path / "skillscope.sqlite"
    snapshot = _seed_store(db_path)
    client = TestClient(build_api_app(db_path))

    responses = (
        (client.get("/api/v1/meta").json(), "StoreMetadata"),
        (client.get("/api/v1/conversations").json(), "ConversationPage"),
        (
            client.get(f"/api/v1/conversations/{snapshot.public_id}").json(),
            "Conversation",
        ),
        (
            client.get("/api/v1/conversations/conv_missing").json(),
            "Error",
        ),
    )

    for body, schema_name in responses:
        _validate(body, schema_name)
