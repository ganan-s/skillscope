"""Application ports for persistence and read projections."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from skillscope.application.queries import (
    ConversationDetail,
    ConversationPage,
    PageRequest,
    StoreMetadata,
)
from skillscope.domain.models import ConversationSnapshot


class ConversationSnapshotWriter(Protocol):
    def persist(self, snapshot: ConversationSnapshot) -> str: ...


class IngestMetadataWriter(Protocol):
    def record_ingest(self, *, completed_at: datetime, summary: object) -> None: ...


class ConversationReader(Protocol):
    def list_conversations(self, request: PageRequest) -> ConversationPage: ...

    def get_conversation(self, public_id: str) -> ConversationDetail | None: ...


class StoreMetadataReader(Protocol):
    def get_store_metadata(self) -> StoreMetadata: ...
