"""Versioned public API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillSource = Literal["user", "cursor-builtin", "agents", "project", "unknown"]
TimeProvenance = Literal["native", "collector_observed", "derived", "missing"]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorResponse(ApiModel):
    code: str
    message: str
    details: dict | None = None


class PayloadResponse(ApiModel):
    status: Literal["captured", "unavailable"]
    content: str | None
    sha256: str | None
    byte_length: int | None
    unavailable_reason: str | None


class ResourceReadResponse(ApiModel):
    id: str
    path: str
    sequence: int
    read_at: datetime | None
    time_provenance: TimeProvenance
    payload: PayloadResponse


class SkillActivationResponse(ApiModel):
    id: str
    task_id: str | None
    turn_index: int | None
    sequence: int
    activated_at: datetime | None
    time_provenance: TimeProvenance
    path: str
    source: SkillSource
    name: str | None
    description: str | None
    payload: PayloadResponse
    resource_reads: list[ResourceReadResponse]


class SkillSummaryResponse(ApiModel):
    name: str | None
    path: str
    source: SkillSource
    activation_count: int


class TaskResponse(ApiModel):
    id: str
    turn_index: int
    text: str
    submitted_at: datetime | None
    time_provenance: TimeProvenance


class ConversationSummaryResponse(ApiModel):
    id: str
    title: str | None
    harness: str
    workspace_paths: list[str]
    started_at: datetime | None
    ended_at: datetime | None
    skills: list[SkillSummaryResponse]
    task_count: int
    activation_count: int


class ConversationResponse(ConversationSummaryResponse):
    tasks: list[TaskResponse]
    skill_activations: list[SkillActivationResponse]


class ConversationPageResponse(ApiModel):
    items: list[ConversationSummaryResponse]
    next_cursor: str | None
    limit: int


class IngestSummaryResponse(ApiModel):
    inserted: int
    updated: int
    unchanged: int
    skipped: int
    failed: int


class StoreMetadataResponse(ApiModel):
    api_version: Literal["v1"]
    schema_version: int
    supported_schema_version: int
    last_successful_ingest_at: datetime | None
    last_ingest_summary: IngestSummaryResponse | None
    harnesses: list[str]


class PaginationParameters(ApiModel):
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
