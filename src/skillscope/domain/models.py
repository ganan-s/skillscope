"""Harness-neutral canonical models for skill-load visibility.

These types define the contract between harness adapters and the ingest/storage
layer.  No Cursor-specific field names, paths, or JSON shapes may appear here.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventType(enum.StrEnum):
    SESSION_CLOSED = "session.closed"
    TASK_RECORDED = "task.recorded"
    SKILL_ACTIVATED = "skill.activated"
    SKILL_ACTIVATION_FAILED = "skill.activation_failed"
    SKILL_RESOURCE_READ = "skill.resource_read"
    TURN_COMPLETED = "turn.completed"


class ActivationFailureReason(enum.StrEnum):
    FAILED = "failed"
    DENIED = "denied"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


class TurnCompletionStatus(enum.StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    UNKNOWN = "unknown"


class ReadinessBasis(enum.StrEnum):
    NATIVE_END = "native_end"
    QUIESCENT = "quiescent"


class TimeProvenance(enum.StrEnum):
    NATIVE = "native"
    COLLECTOR_OBSERVED = "collector_observed"
    DERIVED = "derived"
    MISSING = "missing"


class EvidenceQuality(enum.StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"


class SourceBucket(enum.StrEnum):
    USER = "user"
    CURSOR_BUILTIN = "cursor-builtin"
    AGENTS = "agents"
    PROJECT = "project"
    UNKNOWN = "unknown"


class PayloadStatus(enum.StrEnum):
    CAPTURED = "captured"
    UNAVAILABLE = "unavailable"


class EligibilityVerdict(enum.StrEnum):
    READY = "ready"
    DEFER = "defer"
    REJECT = "reject"


class DiagnosticCode(enum.StrEnum):
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
    source_kind: str  # e.g. "transcript", "hook"
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

    def __post_init__(self) -> None:
        if self.status == PayloadStatus.CAPTURED:
            if self.content is None or self.sha256 is None:
                raise ValueError("captured payload requires content and sha256")
            encoded = self.content.encode()
            if self.byte_length != len(encoded):
                raise ValueError("captured payload byte length does not match content")
            if self.sha256 != hashlib.sha256(encoded).hexdigest():
                raise ValueError("captured payload hash does not match content")
            if self.unavailable_reason is not None:
                raise ValueError("captured payload cannot have an unavailable reason")
        elif (
            self.content is not None
            or self.sha256 is not None
            or not self.unavailable_reason
        ):
            raise ValueError(
                "unavailable payload requires a reason and cannot contain content"
            )


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
_GLOB_CHARACTERS = frozenset("*?[")
_SKILL_MANIFEST_NAME = "SKILL.md"


def is_exact_skill_manifest(path: object) -> bool:
    """Return whether *path* is a concrete exact ``SKILL.md`` file."""
    if not isinstance(path, str) or not path:
        return False
    if any(character in path for character in _GLOB_CHARACTERS):
        return False
    return path.replace("\\", "/").rsplit("/", maxsplit=1)[-1] == _SKILL_MANIFEST_NAME


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

    def __post_init__(self) -> None:
        if self.event_type == EventType.SKILL_ACTIVATION_FAILED:
            path = self.payload.get("path")
            reason = self.payload.get("reason")
            if (
                self.evidence.quality != EvidenceQuality.CONFIRMED
                or not is_exact_skill_manifest(path)
            ):
                raise ValueError("activation failure requires confirmed exact SKILL.md")
            if reason not in ActivationFailureReason:
                raise ValueError("activation failure requires a canonical reason")
        elif self.event_type == EventType.TURN_COMPLETED:
            status = self.payload.get("status")
            if status not in TurnCompletionStatus:
                raise ValueError("turn completion requires a canonical status")

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

    def __post_init__(self) -> None:
        if not self.revision:
            raise ValueError("source revision is required")
        if self.updated_at.tzinfo is None:
            raise ValueError("source revision timestamp must be timezone-aware")


def public_conversation_id(harness_id: str, native_conversation_id: str) -> str:
    """Return a deterministic opaque identifier for a harness conversation."""
    identity = f"{harness_id}\0{native_conversation_id}".encode()
    return f"conv_{hashlib.sha256(identity).hexdigest()[:24]}"


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

    @property
    def public_id(self) -> str:
        return public_conversation_id(
            self.harness_id,
            self.native_conversation_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported canonical contract version")
        if not self.harness_id or not self.native_conversation_id:
            raise ValueError("conversation identity is required")

        event_ids: set[str] = set()
        sequences: set[int] = set()
        activations: dict[str, tuple[int, str]] = {}
        previous_sequence = -1
        for event in self.events:
            if (
                event.harness_id != self.harness_id
                or event.native_conversation_id != self.native_conversation_id
            ):
                raise ValueError("event belongs to another conversation")
            if event.event_id in event_ids:
                raise ValueError("event ids must be unique within a snapshot")
            if event.sequence in sequences or event.sequence <= previous_sequence:
                raise ValueError("event sequences must be unique and strictly ordered")
            if event.turn_index is not None and event.turn_index < 0:
                raise ValueError("turn index cannot be negative")
            event_ids.add(event.event_id)
            sequences.add(event.sequence)
            previous_sequence = event.sequence
            if event.event_type == EventType.SKILL_ACTIVATED:
                path = event.payload.get("path")
                if (
                    event.evidence.quality != EvidenceQuality.CONFIRMED
                    or not is_exact_skill_manifest(path)
                ):
                    raise ValueError(
                        "activation requires confirmed evidence for exact SKILL.md"
                    )
                activations[event.event_id] = (event.sequence, path)
            elif event.event_type == EventType.SKILL_RESOURCE_READ:
                parent_id = event.payload.get("parent_activation_id")
                if (
                    not isinstance(parent_id, str)
                    or parent_id not in activations
                    or activations[parent_id][0] >= event.sequence
                ):
                    raise ValueError(
                        "resource read must reference an earlier activation"
                    )
                resource_path = event.payload.get("path")
                activation_path = activations[parent_id][1].replace("\\", "/")
                skill_directory = activation_path.rsplit("/", maxsplit=1)[0]
                if not isinstance(resource_path, str) or not resource_path.replace(
                    "\\", "/"
                ).startswith(skill_directory + "/"):
                    raise ValueError("resource read must belong to its parent skill")
            if event.event_type in {
                EventType.SKILL_ACTIVATED,
                EventType.SKILL_RESOURCE_READ,
            }:
                payload = event.payload.get("payload_snapshot")
                if isinstance(payload, dict):
                    PayloadSnapshot(
                        status=PayloadStatus(payload.get("status")),
                        content=payload.get("content"),
                        sha256=payload.get("sha256"),
                        byte_length=payload.get("byte_length"),
                        unavailable_reason=payload.get("unavailable_reason"),
                    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "harness_id": self.harness_id,
            "native_conversation_id": self.native_conversation_id,
            "public_id": self.public_id,
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
