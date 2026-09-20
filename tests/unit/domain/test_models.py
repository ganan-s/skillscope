from __future__ import annotations

from datetime import UTC, datetime

import pytest

from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    EventType,
    Evidence,
    EvidenceQuality,
    ReadinessBasis,
    SourceRevision,
)

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


def snapshot(*events: CanonicalEvent) -> ConversationSnapshot:
    return ConversationSnapshot(
        contract_version=CONTRACT_VERSION,
        harness_id="cursor",
        native_conversation_id="conversation-1",
        source_revision=SourceRevision("revision-1", NOW),
        readiness_basis=ReadinessBasis.NATIVE_END,
        events=events,
    )


def event(event_id: str, sequence: int) -> CanonicalEvent:
    return CanonicalEvent(
        contract_version=CONTRACT_VERSION,
        event_id=event_id,
        event_type=EventType.TASK_RECORDED,
        harness_id="cursor",
        native_conversation_id="conversation-1",
        sequence=sequence,
        evidence=Evidence(source_kind="hook", native_event_kind="prompt"),
        payload={"raw_text": "test"},
    )


def test_public_id_when_snapshot_is_recreated_is_stable_and_opaque() -> None:
    first = snapshot()
    second = snapshot()

    assert first.public_id == second.public_id
    assert first.public_id.startswith("conv_")
    assert "conversation-1" not in first.public_id


def test_snapshot_when_event_sequences_repeat_rejects_snapshot() -> None:
    with pytest.raises(ValueError, match="sequences"):
        snapshot(event("one", 1), event("two", 1))


def test_snapshot_when_resource_parent_is_missing_rejects_snapshot() -> None:
    resource = CanonicalEvent(
        contract_version=CONTRACT_VERSION,
        event_id="resource-1",
        event_type=EventType.SKILL_RESOURCE_READ,
        harness_id="cursor",
        native_conversation_id="conversation-1",
        sequence=1,
        evidence=Evidence(source_kind="hook", native_event_kind="postToolUse"),
        payload={
            "parent_activation_id": "activation-missing",
            "path": "/skills/testing/reference.md",
        },
    )

    with pytest.raises(ValueError, match="earlier activation"):
        snapshot(resource)


def test_snapshot_when_activation_failure_is_confirmed_accepts_event() -> None:
    failed = CanonicalEvent(
        contract_version=CONTRACT_VERSION,
        event_id="fail-1",
        event_type=EventType.SKILL_ACTIVATION_FAILED,
        harness_id="cursor",
        native_conversation_id="conversation-1",
        sequence=1,
        evidence=Evidence(
            source_kind="hook",
            native_event_kind="read_failed",
            quality=EvidenceQuality.CONFIRMED,
        ),
        payload={"path": "/skills/testing/SKILL.md", "reason": "failed"},
    )

    assert snapshot(failed).events[0].event_type == EventType.SKILL_ACTIVATION_FAILED


def test_snapshot_when_activation_failure_is_inferred_rejects_event() -> None:
    failed = CanonicalEvent(
        contract_version=CONTRACT_VERSION,
        event_id="fail-1",
        event_type=EventType.SKILL_ACTIVATION_FAILED,
        harness_id="cursor",
        native_conversation_id="conversation-1",
        sequence=1,
        evidence=Evidence(
            source_kind="hook",
            native_event_kind="read_failed",
            quality=EvidenceQuality.INFERRED,
        ),
        payload={"path": "/skills/testing/SKILL.md", "reason": "failed"},
    )

    with pytest.raises(ValueError, match="activation failure requires"):
        snapshot(failed)


def test_snapshot_when_turn_status_is_invalid_rejects_event() -> None:
    completed = CanonicalEvent(
        contract_version=CONTRACT_VERSION,
        event_id="turn-1",
        event_type=EventType.TURN_COMPLETED,
        harness_id="cursor",
        native_conversation_id="conversation-1",
        sequence=1,
        evidence=Evidence(source_kind="transcript", native_event_kind="turn_ended"),
        payload={"status": "crashed"},
    )

    with pytest.raises(ValueError, match="canonical status"):
        snapshot(completed)
