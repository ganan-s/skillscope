"""Evaluate explicit project expectations without inferring adherence from reads."""

from __future__ import annotations

import re
from typing import Protocol

from skillscope.domain.evaluation import (
    BehaviorReview,
    CaseEvidence,
    CaseResult,
    Citation,
    EvaluationCase,
    EvaluationError,
    EvaluationInputs,
    EvaluationReport,
    EvidenceBundle,
    Finding,
    SelectionReview,
)


class EvaluationSource(Protocol):
    def load(self) -> EvaluationInputs: ...


class EvaluationSink(Protocol):
    def save(self, report: EvaluationReport) -> None: ...


class EvaluateSkills:
    def __init__(self, source: EvaluationSource, sink: EvaluationSink) -> None:
        self.source = source
        self.sink = sink

    def __call__(self, *, created_at: str) -> EvaluationReport:
        inputs = self.source.load()
        validate_inputs(inputs)
        evidence = (
            {e.case_id: e for e in inputs.evidence.cases} if inputs.evidence else {}
        )
        report = EvaluationReport(
            schema_version=1,
            created_at=created_at,
            inputs=inputs,
            static_findings=_static_findings(inputs),
            cases=tuple(
                _evaluate_case(case, evidence.get(case.id), inputs.evidence)
                for case in inputs.case_set.cases
            ),
            limitations=(
                "Expectations are proposed project specifications, "
                "not historical failures.",
                "Reviewed findings are supplied reviewer judgments; "
                "identity and runtime "
                "authenticity are not independently verified.",
                "Supplied reads are observations only. Missing or extra reads do not "
                "establish missed selection, over-selection, adherence, "
                "or effectiveness.",
                "Illustrations and agent self-reports cannot establish compliance.",
                "No agent run is launched. Behavioral improvement and causality remain "
                "unverified, including when a static inconsistency is removed.",
            ),
        )
        self.sink.save(report)
        return report


def _unique(values: tuple[str, ...], label: str) -> None:
    if any(not value.strip() for value in values) or len(values) != len(set(values)):
        raise EvaluationError(f"Empty or duplicate {label}")


def validate_inputs(inputs: EvaluationInputs) -> None:
    spec = inputs.case_set
    _unique(tuple(s.id for s in spec.skills), "skill IDs")
    _unique(tuple(s.path for s in spec.skills), "skill paths")
    _unique(tuple(c.id for c in spec.cases), "case IDs")
    if not spec.skills or not spec.cases:
        raise EvaluationError("A case set needs skills and cases")
    skills = {s.id for s in spec.skills}
    sources = {s.path: s.content for s in inputs.sources}
    for case in spec.cases:
        groups = (case.required_skills, case.allowed_skills, case.forbidden_skills)
        _unique(tuple(s for group in groups for s in group), "case skill roles")
        if not set((*case.required_skills, *case.forbidden_skills)) <= skills:
            raise EvaluationError(f"Unknown skill in {case.id}")
        _unique(tuple(r.id for r in case.requirements), "requirement IDs")
        refs = (
            *case.source_refs,
            *(ref for r in case.requirements for ref in r.source_refs),
        )
        if not case.source_refs or any(not r.source_refs for r in case.requirements):
            raise EvaluationError(f"Missing expectation provenance in {case.id}")
        for ref in refs:
            if not ref.quote.strip() or ref.quote not in sources.get(ref.path, ""):
                raise EvaluationError(f"Stale source quote in {case.id}: {ref.path}")
    bundle = inputs.evidence
    if bundle is None:
        return
    if (
        bundle.case_set_sha256 != inputs.case_set_snapshot.sha256
        or bundle.source_snapshot_sha256 != inputs.source_snapshot_sha256
    ):
        raise EvaluationError(
            "Evidence version mismatch: recapture/review against these inputs"
        )
    _unique(tuple(e.case_id for e in bundle.cases), "evidence case IDs")
    _unique(tuple(a.id for a in bundle.artifacts), "artifact IDs")
    artifacts = {a.path: a.content for a in inputs.artifacts}
    if any(a.path not in artifacts for a in bundle.artifacts):
        raise EvaluationError("Missing artifact snapshot")
    artifact_contents = {a.id: artifacts[a.path] for a in bundle.artifacts}
    if bundle.context.workspace_revision != inputs.project_revision:
        raise EvaluationError("Evidence project revision mismatch")
    cases = {c.id: c for c in spec.cases}
    for entry in bundle.cases:
        if entry.case_id not in cases:
            raise EvaluationError(f"Unknown evidence case: {entry.case_id}")
        case = cases[entry.case_id]
        _unique(tuple(c.requirement_id for c in entry.checks), "reviewed requirements")
        if not {c.requirement_id for c in entry.checks} <= {
            r.id for r in case.requirements
        }:
            raise EvaluationError(f"Unknown requirement in {entry.case_id}")
        for read in entry.reads:
            if read.skill_id not in skills:
                raise EvaluationError(f"Unknown observed pilot skill: {read.skill_id}")
            _validate_citations((read.evidence,), artifact_contents)
        reviews = (*entry.checks, *((entry.selection,) if entry.selection else ()))
        for review in reviews:
            if not review.rationale.strip():
                raise EvaluationError("Every review needs a rationale")
            if review.basis == "human_review" and not (review.reviewer or "").strip():
                raise EvaluationError("Human review requires a named reviewer")
            _validate_citations(review.evidence, artifact_contents)
        if entry.selection:
            _unique(entry.selection.assessed_skills, "assessed skills")


def _validate_citations(
    citations: tuple[Citation, ...], artifacts: dict[str, str]
) -> None:
    if not citations:
        raise EvaluationError("A supplied claim needs an artifact citation")
    for citation in citations:
        if not citation.quote.strip() or citation.quote not in artifacts.get(
            citation.artifact_id, ""
        ):
            raise EvaluationError(
                f"Missing artifact or exact excerpt: {citation.artifact_id}"
            )


def _review_status(
    review: BehaviorReview | SelectionReview, outcome: str, bundle: EvidenceBundle
) -> str:
    illustrated = {a.id for a in bundle.artifacts if a.provenance == "illustrative"}
    if (
        review.basis == "illustrative"
        or bundle.provenance == "illustrative"
        or any(ref.artifact_id in illustrated for ref in review.evidence)
    ):
        return "illustrative_only"
    if review.basis == "agent_self_report":
        return "unsupported_self_report"
    context = bundle.context
    if any(
        value.strip().lower()
        in {"", "not-run", "not-recorded", "unknown", "unavailable"}
        for value in (
            context.runtime,
            context.model,
            context.environment,
            context.invocation,
            context.workspace_revision,
        )
    ):
        return "inconclusive"
    return "inconclusive" if outcome == "unknown" else f"reviewed_{outcome}"


def _evaluate_case(
    case: EvaluationCase, evidence: CaseEvidence | None, bundle: EvidenceBundle | None
) -> CaseResult:
    review = evidence.selection if evidence else None
    selection = Finding(
        "selection", "missing_evidence", "No reviewed applicability assessment."
    )
    if review and bundle:
        assessed = set(review.assessed_skills)
        missing = set(case.required_skills) - assessed
        forbidden = set(case.forbidden_skills) & assessed
        unexplained = assessed - set(case.required_skills) - set(case.allowed_skills)
        # Other skills (for example architecture) are deliberately unrestricted.
        outcome = "met" if not missing and not forbidden else "not_met"
        if not review.complete:
            outcome = "unknown"
        selection = Finding(
            "selection",
            _review_status(review, outcome, bundle),
            f"Supplied assessment: {outcome} ({review.basis}; "
            f"reviewer: {review.reviewer}). "
            f"{review.rationale} Missing required applicability: {sorted(missing)}; "
            f"forbidden applicability: {sorted(forbidden)}. Other assessed skills "
            f"are not penalized: {sorted(unexplained - forbidden)}. "
            "This compares a supplied applicability judgment, not load completeness.",
            review.evidence,
        )
    checks = {c.requirement_id: c for c in evidence.checks} if evidence else {}
    behavior = []
    for requirement in case.requirements:
        check = checks.get(requirement.id)
        behavior.append(
            Finding(
                requirement.id,
                _review_status(check, check.outcome, bundle)
                if check and bundle
                else "missing_evidence",
                (
                    f"Supplied outcome: {check.outcome} ({check.basis}; "
                    f"reviewer: {check.reviewer}). {check.rationale}"
                )
                if check
                else f"Needs artifact/execution review: {requirement.description}",
                check.evidence if check else (),
            )
        )
    return CaseResult(
        case.id, selection, tuple(behavior), evidence.reads if evidence else ()
    )


def _static_findings(inputs: EvaluationInputs) -> tuple[Finding, ...]:
    sources = {s.path: s.content for s in inputs.sources}
    rule = "Use uv for Python environments, dependencies, and commands."
    if rule not in sources.get("AGENTS.md", ""):
        return (
            Finding(
                "project",
                "not_checked",
                "The pilot's explicit AGENTS uv rule was not found.",
            ),
        )
    findings = []
    for skill in inputs.case_set.skills:
        bare_commands = []
        in_shell = False
        for number, line in enumerate(sources[skill.path].splitlines(), 1):
            if line.strip().startswith("```"):
                in_shell = not in_shell and line.strip() in {
                    "```bash",
                    "```sh",
                    "```shell",
                }
            elif in_shell and re.match(r"^\s*(?:\$ )?pytest(?:\s|$)", line):
                bare_commands.append((number, line.strip()))
        if bare_commands:
            for number, command in bare_commands:
                findings.append(
                    Finding(
                        skill.id,
                        "static_inconsistency",
                        f"{skill.path}:{number} shows `{command}` "
                        "while AGENTS.md requires uv. "
                        f"Propose `uv run {command}`; command consistency only, "
                        "behavior unverified.",
                        (Citation(skill.path, command), Citation("AGENTS.md", rule)),
                    )
                )
        else:
            findings.append(
                Finding(
                    skill.id,
                    "static_check_clear",
                    "No bare pytest invocation in shell fences. "
                    "This narrow text check does not "
                    "establish command compliance or general skill quality.",
                )
            )
    return tuple(findings)
