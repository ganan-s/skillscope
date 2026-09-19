"""Harness-neutral canonical models for skill-load visibility.

These types define the contract between harness adapters and the ingest/storage
layer.  No Cursor-specific field names, paths, or JSON shapes may appear here.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EventType(str, enum.Enum):
    SESSION_CLOSED = "session.closed"
    TASK_RECORDED = "task.recorded"
    SKILL_ACTIVATED = "skill.activated"
    SKILL_RESOURCE_READ = "skill.resource_read"


class ReadinessBasis(str, enum.Enum):
    NATIVE_END = "native_end"
    QUIESCENT = "quiescent"


class TimeProvenance(str, enum.Enum):
    NATIVE = "native"
    COLLECTOR_OBSERVED = "collector_observed"
    DERIVED = "derived"
    MISSING = "missing"


class EvidenceQuality(str, enum.Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"


class SourceBucket(str, enum.Enum):
    USER = "user"
    CURSOR_BUILTIN = "cursor-builtin"
    AGENTS = "agents"
    PROJECT = "project"
    UNKNOWN = "unknown"


class PayloadStatus(str, enum.Enum):
    CAPTURED = "captured"
    UNAVAILABLE = "unavailable"


class EligibilityVerdict(str, enum.Enum):
    READY = "ready"
    DEFER = "defer"
    REJECT = "reject"


class DiagnosticCode(str, enum.Enum):
    READ_OUTCOME_UNKNOWN = "read_outcome_unknown"
    READ_FAILED = "read_failed"
    PAYLOAD_UNAVAILABLE = "payload_unavailable"
    FRONTMATTER_INVALID = "frontmatter_invalid"
    SESSION_ACTIVE = "session_active"
    TRANSCRIPT_TRUNCATED = "transcript_truncated"
    METADATA_MISSING = "metadata_missing"
    NATIVE_RECORD_UNSUPPORTED = "native_record_unsupported"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    source_kind: str          # e.g. "transcript", "hook"
    native_event_kind: str
    native_event_id: str | None = None
    redacted_locator: str | None = None
    record_position: int | None = None
    harness_version: str | None = None
    quality: EvidenceQuality = EvidenceQuality.CONFIRMED


@dataclass(frozen=True)
class PayloadSnapshot:
    status: PayloadStatus
    content: str | None = None
    sha256: str | None = None
    byte_length: int | None = None
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class Diagnostic:
    code: DiagnosticCode
    message: str
    path: str | None = None
    record_position: int | None = None


# ---------------------------------------------------------------------------
# Canonical event envelope
# ---------------------------------------------------------------------------

CONTRACT_VERSION = 1

@dataclass(frozen=True)
class CanonicalEvent:
    contract_version: int
    event_id: str
    event_type: EventType
    harness_id: str
    native_conversation_id: str
    sequence: int
    evidence: Evidence
    native_turn_id: str | None = None
    turn_index: int | None = None
    occurred_at: datetime | None = None
    time_provenance: TimeProvenance = TimeProvenance.MISSING
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Stable JSON-serialisable dict for persistence and tests."""
        d: dict[str, Any] = {}
        for f in dataclasses.fields(self):
            val = getattr(self, f.name)
            if isinstance(val, enum.Enum):
                d[f.name] = val.value
            elif isinstance(val, datetime):
                d[f.name] = val.isoformat()
            elif dataclasses.is_dataclass(val) and not isinstance(val, type):
                d[f.name] = {
                    k: (v.value if isinstance(v, enum.Enum) else v)
                    for k, v in dataclasses.asdict(val).items()
                }
            else:
                d[f.name] = val
        return d


# ---------------------------------------------------------------------------
# Conversation snapshot aggregate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceRevision:
    """Opaque revision for idempotent upsert."""
    revision: str
    updated_at: datetime


@dataclass(frozen=True)
class ConversationSnapshot:
    contract_version: int
    harness_id: str
    native_conversation_id: str
    source_revision: SourceRevision
    readiness_basis: ReadinessBasis
    events: tuple[CanonicalEvent, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    title: str | None = None
    workspace_paths: tuple[str, ...] = ()
    started_at: datetime | None = None
    ended_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "harness_id": self.harness_id,
            "native_conversation_id": self.native_conversation_id,
            "source_revision": {
                "revision": self.source_revision.revision,
                "updated_at": self.source_revision.updated_at.isoformat(),
            },
            "readiness_basis": self.readiness_basis.value,
            "title": self.title,
            "workspace_paths": list(self.workspace_paths),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "events": [e.to_dict() for e in self.events],
            "diagnostics": [dataclasses.asdict(d) for d in self.diagnostics],
        }


# ---------------------------------------------------------------------------
# Ingest eligibility
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IngestEligibility:
    verdict: EligibilityVerdict
    basis: ReadinessBasis | None = None
    reason: str | None = None
