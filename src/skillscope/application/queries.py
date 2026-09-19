"""Read-only application query models and use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skillscope.application.ports import ConversationReader, StoreMetadataReader


class ApplicationError(Exception):
    """Base class for stable application failures."""


class ConversationNotFoundError(ApplicationError):
    pass


class InvalidPaginationError(ApplicationError):
    pass


class StoreError(ApplicationError):
    code = "store_unreadable"


class StoreMissingError(StoreError):
    code = "store_missing"


class StoreIncompatibleError(StoreError):
    code = "store_incompatible"


@dataclass(frozen=True)
class PageRequest:
    cursor: str | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100:
            raise InvalidPaginationError("limit must be between 1 and 100")


@dataclass(frozen=True)
class Payload:
    status: str
    content: str | None
    sha256: str | None
    byte_length: int | None
    unavailable_reason: str | None


@dataclass(frozen=True)
class SkillResourceRead:
    id: str
    path: str
    sequence: int
    read_at: datetime | None
    time_provenance: str
    payload: Payload


@dataclass(frozen=True)
class SkillActivation:
    id: str
    task_id: str | None
    turn_index: int | None
    sequence: int
    activated_at: datetime | None
    time_provenance: str
    path: str
    source: str
    name: str | None
    description: str | None
    payload: Payload
    resource_reads: tuple[SkillResourceRead, ...] = ()


@dataclass(frozen=True)
class SkillSummary:
    name: str | None
    path: str
    source: str
    activation_count: int


@dataclass(frozen=True)
class Task:
    id: str
    turn_index: int
    text: str
    submitted_at: datetime | None
    time_provenance: str


@dataclass(frozen=True)
class ConversationSummary:
    id: str
    title: str | None
    harness: str
    workspace_paths: tuple[str, ...]
    started_at: datetime | None
    ended_at: datetime | None
    skills: tuple[SkillSummary, ...]
    task_count: int
    activation_count: int


@dataclass(frozen=True)
class ConversationDetail(ConversationSummary):
    tasks: tuple[Task, ...]
    skill_activations: tuple[SkillActivation, ...]


@dataclass(frozen=True)
class ConversationPage:
    items: tuple[ConversationSummary, ...]
    next_cursor: str | None
    limit: int


@dataclass(frozen=True)
class IngestCounts:
    inserted: int
    updated: int
    unchanged: int
    skipped: int
    failed: int


@dataclass(frozen=True)
class StoreMetadata:
    api_version: str
    schema_version: int
    supported_schema_version: int
    last_successful_ingest_at: datetime | None
    last_ingest_summary: IngestCounts | None
    harnesses: tuple[str, ...]


class ListConversations:
    def __init__(self, reader: ConversationReader) -> None:
        self._reader = reader

    def __call__(self, request: PageRequest) -> ConversationPage:
        return self._reader.list_conversations(request)


class GetConversation:
    def __init__(self, reader: ConversationReader) -> None:
        self._reader = reader

    def __call__(self, public_id: str) -> ConversationDetail:
        conversation = self._reader.get_conversation(public_id)
        if conversation is None:
            raise ConversationNotFoundError(public_id)
        return conversation


class GetStoreMetadata:
    def __init__(self, reader: StoreMetadataReader) -> None:
        self._reader = reader

    def __call__(self) -> StoreMetadata:
        return self._reader.get_store_metadata()
