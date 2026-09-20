from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skillscope.application.ingest import IngestConversations
from skillscope.application.ports import (
    ConversationRef,
    DiscoveryContext,
    IngestMetadata,
    Platform,
)
from skillscope.domain.models import (
    CONTRACT_VERSION,
    CanonicalEvent,
    ConversationSnapshot,
    EligibilityVerdict,
    EventType,
    Evidence,
    IngestEligibility,
    ReadinessBasis,
    SourceRevision,
)

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


class FakePlugin:
    id = "test"

    def detect_platform(self) -> Platform:
        return Platform(os="linux", harness=self.id)

    def discover(self, context: DiscoveryContext) -> list[ConversationRef]:
        return [
            ConversationRef(self.id, "ready"),
            ConversationRef(self.id, "active"),
        ]

    def inspect(
        self,
        conversation: ConversationRef,
        *,
        now: datetime,
        context: DiscoveryContext,
    ) -> IngestEligibility:
        if conversation.native_conversation_id == "active":
            return IngestEligibility(verdict=EligibilityVerdict.DEFER)
        return IngestEligibility(
            verdict=EligibilityVerdict.READY,
            basis=ReadinessBasis.NATIVE_END,
        )

    def snapshot(
        self,
        conversation: ConversationRef,
        *,
        context: DiscoveryContext,
    ) -> ConversationSnapshot:
        return ConversationSnapshot(
            contract_version=CONTRACT_VERSION,
            harness_id=self.id,
            native_conversation_id=conversation.native_conversation_id,
            source_revision=SourceRevision("revision-1", NOW),
            readiness_basis=ReadinessBasis.NATIVE_END,
            events=(),
        )


class FakeWriter:
    def __init__(self) -> None:
        self.snapshots: list[ConversationSnapshot] = []
        self.completed_at: datetime | None = None

    def persist(self, snapshot: ConversationSnapshot) -> str:
        self.snapshots.append(snapshot)
        return "inserted"

    def record_ingest(
        self,
        *,
        completed_at: datetime,
        summary: IngestMetadata,
    ) -> None:
        self.completed_at = completed_at


class FailingWriter(FakeWriter):
    def persist(self, snapshot: ConversationSnapshot) -> str:
        raise OSError("/private/transcript/path")


def test_ingest_when_sources_are_ready_and_active_persists_only_ready() -> None:
    writer = FakeWriter()
    operation = IngestConversations(
        plugin=FakePlugin(),
        writer=writer,
        metadata_writer=writer,
    )
    context = DiscoveryContext(home=Path("/home/test"), user_data=Path("/data"))

    result = operation(context=context, now=NOW)

    assert result.inserted == 1
    assert result.deferred == 1
    assert [item.native_conversation_id for item in writer.snapshots] == ["ready"]
    assert writer.completed_at == NOW


def test_ingest_when_adapter_fails_redacts_internal_error_details() -> None:
    writer = FailingWriter()
    operation = IngestConversations(
        plugin=FakePlugin(),
        writer=writer,
        metadata_writer=writer,
    )
    context = DiscoveryContext(home=Path("/home/test"), user_data=Path("/data"))

    result = operation(context=context, now=NOW)

    assert result.failed == 1
    assert result.errors == ["ready: ingestion_failed"]


class EffectivenessPlugin(FakePlugin):
    def discover(self, context: DiscoveryContext) -> list[ConversationRef]:
        return [ConversationRef(self.id, "ready")]

    def snapshot(
        self,
        conversation: ConversationRef,
        *,
        context: DiscoveryContext,
    ) -> ConversationSnapshot:
        return ConversationSnapshot(
            contract_version=CONTRACT_VERSION,
            harness_id=self.id,
            native_conversation_id=conversation.native_conversation_id,
            source_revision=SourceRevision("revision-1", NOW),
            readiness_basis=ReadinessBasis.NATIVE_END,
            events=(
                CanonicalEvent(
                    contract_version=CONTRACT_VERSION,
                    event_id="fail-1",
                    event_type=EventType.SKILL_ACTIVATION_FAILED,
                    harness_id=self.id,
                    native_conversation_id=conversation.native_conversation_id,
                    sequence=1,
                    evidence=Evidence(
                        source_kind="hook",
                        native_event_kind="read_failed",
                    ),
                    payload={
                        "path": "/skills/testing/SKILL.md",
                        "reason": "failed",
                    },
                ),
                CanonicalEvent(
                    contract_version=CONTRACT_VERSION,
                    event_id="turn-1",
                    event_type=EventType.TURN_COMPLETED,
                    harness_id=self.id,
                    native_conversation_id=conversation.native_conversation_id,
                    sequence=2,
                    evidence=Evidence(
                        source_kind="transcript",
                        native_event_kind="turn_ended",
                    ),
                    payload={"status": "error"},
                ),
            ),
        )


def test_ingest_when_snapshot_has_effectiveness_events_persists_them() -> None:
    writer = FakeWriter()
    operation = IngestConversations(
        plugin=EffectivenessPlugin(),
        writer=writer,
        metadata_writer=writer,
    )
    context = DiscoveryContext(home=Path("/home/test"), user_data=Path("/data"))

    result = operation(context=context, now=NOW)

    assert result.inserted == 1
    events = writer.snapshots[0].events
    assert [event.event_type for event in events] == [
        EventType.SKILL_ACTIVATION_FAILED,
        EventType.TURN_COMPLETED,
    ]
