"""Application ports for persistence and read projections."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from skillscope.application.queries import (
    ConversationDetail,
    ConversationPage,
    PageRequest,
    StoreMetadata,
)
from skillscope.domain.models import ConversationSnapshot, IngestEligibility


@dataclass(frozen=True)
class Platform:
    os: str
    harness: str


@dataclass(frozen=True)
class DiscoveryContext:
    """Runtime configuration supplied by core to a harness adapter."""

    home: Path
    user_data: Path
    transcript_override: Path | None = None
    spool_override: Path | None = None
    contract_version: int = 1
    grace_seconds: int = 300


@dataclass(frozen=True)
class ConversationRef:
    """Opaque harness-owned reference to one native conversation."""

    harness_id: str
    native_conversation_id: str
    source_locators: tuple[Path, ...] = ()
    extra: dict = field(default_factory=dict)


@runtime_checkable
class HarnessPlugin(Protocol):
    @property
    def id(self) -> str: ...

    def detect_platform(self) -> Platform: ...

    def discover(self, context: DiscoveryContext) -> Iterable[ConversationRef]: ...

    def inspect(
        self,
        conversation: ConversationRef,
        *,
        now: datetime,
        context: DiscoveryContext,
    ) -> IngestEligibility: ...

    def snapshot(
        self,
        conversation: ConversationRef,
        *,
        context: DiscoveryContext,
    ) -> ConversationSnapshot: ...


@dataclass(frozen=True)
class IngestMetadata:
    inserted: int
    updated: int
    unchanged: int
    skipped: int
    failed: int

    @property
    def processed_snapshots(self) -> int:
        return self.inserted + self.updated + self.unchanged


class ConversationSnapshotWriter(Protocol):
    def persist(self, snapshot: ConversationSnapshot) -> str: ...


class IngestMetadataWriter(Protocol):
    def record_ingest(
        self,
        *,
        completed_at: datetime,
        summary: IngestMetadata,
    ) -> None: ...


class ConversationReader(Protocol):
    def list_conversations(self, request: PageRequest) -> ConversationPage: ...

    def get_conversation(self, public_id: str) -> ConversationDetail | None: ...


class StoreMetadataReader(Protocol):
    def get_store_metadata(self) -> StoreMetadata: ...
