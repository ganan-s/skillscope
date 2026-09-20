"""Portable evaluation specifications, evidence, and findings.

Reviewed judgments are attestations, never independently confirmed behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class EvaluationError(ValueError):
    """An invalid or incompatible evaluation input."""


@dataclass(frozen=True)
class SourceRef:
    path: str
    quote: str


@dataclass(frozen=True)
class SkillSpec:
    id: str
    path: str


@dataclass(frozen=True)
class Requirement:
    id: str
    description: str
    source_refs: tuple[SourceRef, ...]


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    title: str
    task: str
    required_skills: tuple[str, ...]
    allowed_skills: tuple[str, ...]
    forbidden_skills: tuple[str, ...]
    requirements: tuple[Requirement, ...]
    selection_rationale: str
    source_refs: tuple[SourceRef, ...]


@dataclass(frozen=True)
class CaseProvenance:
    kind: Literal["project_specification"]
    note: str


@dataclass(frozen=True)
class CaseSet:
    schema_version: Literal[1]
    id: str
    version: str
    provenance: CaseProvenance
    skills: tuple[SkillSpec, ...]
    cases: tuple[EvaluationCase, ...]


@dataclass(frozen=True)
class Citation:
    artifact_id: str
    quote: str


Basis = Literal["human_review", "illustrative", "agent_self_report"]


@dataclass(frozen=True)
class SelectionReview:
    basis: Basis
    assessed_skills: tuple[str, ...]
    complete: bool
    rationale: str
    reviewer: str | None
    evidence: tuple[Citation, ...]


@dataclass(frozen=True)
class BehaviorReview:
    requirement_id: str
    basis: Basis
    outcome: Literal["met", "not_met", "unknown"]
    rationale: str
    reviewer: str | None
    evidence: tuple[Citation, ...]


@dataclass(frozen=True)
class ReadObservation:
    skill_id: str
    evidence: Citation


@dataclass(frozen=True)
class CaseEvidence:
    case_id: str
    reads: tuple[ReadObservation, ...]
    selection: SelectionReview | None
    checks: tuple[BehaviorReview, ...]


@dataclass(frozen=True)
class ArtifactRef:
    id: str
    path: str
    description: str
    provenance: Literal["supplied_capture", "illustrative"]


@dataclass(frozen=True)
class RunContext:
    runtime: str
    model: str
    environment: str
    invocation: str
    workspace_revision: str


@dataclass(frozen=True)
class EvidenceBundle:
    schema_version: Literal[1]
    run_id: str
    provenance: Literal["supplied_capture", "illustrative"]
    case_set_sha256: str
    source_snapshot_sha256: str
    context: RunContext
    artifacts: tuple[ArtifactRef, ...]
    cases: tuple[CaseEvidence, ...]


@dataclass(frozen=True)
class TextSnapshot:
    path: str
    sha256: str
    content: str


@dataclass(frozen=True)
class EvaluationInputs:
    case_set: CaseSet
    case_set_snapshot: TextSnapshot
    sources: tuple[TextSnapshot, ...]
    source_snapshot_sha256: str
    project_revision: str
    project_dirty_paths: tuple[str, ...]
    evidence: EvidenceBundle | None = None
    evidence_snapshot: TextSnapshot | None = None
    artifacts: tuple[TextSnapshot, ...] = ()


@dataclass(frozen=True)
class Finding:
    subject: str
    status: str
    explanation: str
    evidence: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    selection: Finding
    behavior: tuple[Finding, ...]
    observed_reads: tuple[ReadObservation, ...]


@dataclass(frozen=True)
class EvaluationReport:
    schema_version: int
    created_at: str
    inputs: EvaluationInputs
    static_findings: tuple[Finding, ...]
    cases: tuple[CaseResult, ...]
    limitations: tuple[str, ...]
