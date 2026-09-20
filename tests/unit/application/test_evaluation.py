from __future__ import annotations

from dataclasses import replace

import pytest

from skillscope.application.evaluation import EvaluateSkills
from skillscope.domain.evaluation import (
    ArtifactRef,
    BehaviorReview,
    CaseEvidence,
    CaseProvenance,
    CaseSet,
    Citation,
    EvaluationCase,
    EvaluationError,
    EvaluationInputs,
    EvaluationReport,
    EvidenceBundle,
    ReadObservation,
    Requirement,
    RunContext,
    SelectionReview,
    SkillSpec,
    SourceRef,
    TextSnapshot,
)

SKILL_PATH = ".cursor/skills/backend-unit-testing/SKILL.md"
UV_RULE = "Use uv for Python environments, dependencies, and commands."
SOURCE_QUOTE = "Unit tests perform no filesystem I/O."
ARTIFACT_QUOTE = "Reviewed the parser test: all inputs are in-memory."
CITATION = Citation("review-artifact", ARTIFACT_QUOTE)


class MemorySource:
    def __init__(self, inputs: EvaluationInputs) -> None:
        self.inputs = inputs

    def load(self) -> EvaluationInputs:
        return self.inputs


class MemorySink:
    def __init__(self) -> None:
        self.reports: list[EvaluationReport] = []

    def save(self, report: EvaluationReport) -> None:
        self.reports.append(report)


def evaluation_inputs(*, skill_content: str = SOURCE_QUOTE) -> EvaluationInputs:
    source = SourceRef(SKILL_PATH, SOURCE_QUOTE)
    case = EvaluationCase(
        id="pure-parser",
        title="Pure parser test",
        task="Test a parser with in-memory records.",
        required_skills=("backend-unit-testing",),
        allowed_skills=("backend-hexagonal-architecture",),
        forbidden_skills=("backend-integration-testing",),
        requirements=(Requirement("no-io", "Keep test inputs in memory.", (source,)),),
        selection_rationale="A pure parser test has no infrastructure boundary.",
        source_refs=(source,),
    )
    case_set = CaseSet(
        schema_version=1,
        id="testing-pilot",
        version="1.0",
        provenance=CaseProvenance("project_specification", "Proposed expectations."),
        skills=(
            SkillSpec("backend-unit-testing", SKILL_PATH),
            SkillSpec("backend-integration-testing", "integration/SKILL.md"),
            SkillSpec("backend-hexagonal-architecture", "architecture/SKILL.md"),
        ),
        cases=(case,),
    )
    return EvaluationInputs(
        case_set=case_set,
        case_set_snapshot=TextSnapshot("cases.json", "case-hash", "case bytes"),
        sources=(
            TextSnapshot(SKILL_PATH, "unit-hash", skill_content),
            TextSnapshot("integration/SKILL.md", "integration-hash", "Integration"),
            TextSnapshot("architecture/SKILL.md", "architecture-hash", "Architecture"),
            TextSnapshot("AGENTS.md", "agents-hash", UV_RULE),
        ),
        source_snapshot_sha256="source-hash",
        project_revision="test-revision",
        project_dirty_paths=(),
    )


def reviewed_selection(
    *, assessed: tuple[str, ...] = ("backend-unit-testing",), complete: bool = True
) -> SelectionReview:
    return SelectionReview(
        basis="human_review",
        assessed_skills=assessed,
        complete=complete,
        rationale="Reviewed the task and applicable skill boundaries.",
        reviewer="Synthetic test reviewer",
        evidence=(CITATION,),
    )


def reviewed_behavior() -> BehaviorReview:
    return BehaviorReview(
        requirement_id="no-io",
        basis="human_review",
        outcome="met",
        rationale="Reviewed the resulting test and its inputs.",
        reviewer="Synthetic test reviewer",
        evidence=(CITATION,),
    )


def with_evidence(inputs: EvaluationInputs, entry: CaseEvidence) -> EvaluationInputs:
    bundle = EvidenceBundle(
        schema_version=1,
        run_id="synthetic-review-test",
        provenance="supplied_capture",
        case_set_sha256=inputs.case_set_snapshot.sha256,
        source_snapshot_sha256=inputs.source_snapshot_sha256,
        context=RunContext(
            "test-only", "test-model", "synthetic", "test", "test-revision"
        ),
        artifacts=(
            ArtifactRef(
                "review-artifact",
                "review.txt",
                "Synthetic test artifact",
                "supplied_capture",
            ),
        ),
        cases=(entry,),
    )
    return replace(
        inputs,
        evidence=bundle,
        evidence_snapshot=TextSnapshot(
            "evidence.json", "evidence-hash", "evidence bytes"
        ),
        artifacts=(TextSnapshot("review.txt", "artifact-hash", ARTIFACT_QUOTE),),
    )


def evaluate(inputs: EvaluationInputs) -> EvaluationReport:
    return EvaluateSkills(MemorySource(inputs), MemorySink())(
        created_at="2026-01-01T00:00:00Z"
    )


def test_evaluate_when_evidence_is_missing_preserves_uncertainty_and_saves_report() -> (
    None
):
    inputs = evaluation_inputs()
    sink = MemorySink()

    report = EvaluateSkills(MemorySource(inputs), sink)(
        created_at="2026-01-01T00:00:00Z"
    )

    assert report.cases[0].selection.status == "missing_evidence"
    assert report.cases[0].behavior[0].status == "missing_evidence"
    assert report.cases[0].observed_reads == ()
    assert sink.reports == [report]
    assert report.inputs is inputs
    assert any("causality remain unverified" in note for note in report.limitations)


def test_evaluate_when_only_read_is_supplied_does_not_infer_selection_or_behavior() -> (
    None
):
    observation = ReadObservation("backend-unit-testing", CITATION)
    inputs = with_evidence(
        evaluation_inputs(), CaseEvidence("pure-parser", (observation,), None, ())
    )

    report = evaluate(inputs)

    assert report.cases[0].observed_reads == (observation,)
    assert report.cases[0].selection.status == "missing_evidence"
    assert report.cases[0].behavior[0].status == "missing_evidence"


@pytest.mark.parametrize(
    "co_used_skill",
    ["backend-hexagonal-architecture", "another-project-skill"],
    ids=["explicitly-allowed", "outside-pilot"],
)
def test_evaluate_when_review_allows_co_use_keeps_review_distinct_from_confirmation(
    co_used_skill: str,
) -> None:
    selection = reviewed_selection(assessed=("backend-unit-testing", co_used_skill))
    inputs = with_evidence(
        evaluation_inputs(),
        CaseEvidence("pure-parser", (), selection, (reviewed_behavior(),)),
    )

    report = evaluate(inputs)

    assert report.cases[0].selection.status == "reviewed_met"
    assert report.cases[0].behavior[0].status == "reviewed_met"
    assert report.cases[0].selection.evidence == (CITATION,)
    assert any("not independently verified" in note for note in report.limitations)


@pytest.mark.parametrize(
    "assessed",
    [(), ("backend-unit-testing", "backend-integration-testing")],
    ids=["missing-required", "forbidden-applies"],
)
def test_evaluate_when_complete_review_disagrees_reports_reviewed_not_met(
    assessed: tuple[str, ...],
) -> None:
    inputs = with_evidence(
        evaluation_inputs(),
        CaseEvidence("pure-parser", (), reviewed_selection(assessed=assessed), ()),
    )

    report = evaluate(inputs)

    assert report.cases[0].selection.status == "reviewed_not_met"


@pytest.mark.parametrize("assessed", [(), ("backend-unit-testing",)])
def test_evaluate_when_selection_review_is_incomplete_reports_inconclusive(
    assessed: tuple[str, ...],
) -> None:
    inputs = with_evidence(
        evaluation_inputs(),
        CaseEvidence(
            "pure-parser", (), reviewed_selection(assessed=assessed, complete=False), ()
        ),
    )

    report = evaluate(inputs)

    assert report.cases[0].selection.status == "inconclusive"


@pytest.mark.parametrize(
    ("basis", "status"),
    [
        ("illustrative", "illustrative_only"),
        ("agent_self_report", "unsupported_self_report"),
    ],
)
def test_evaluate_when_claim_is_unverified_never_reports_reviewed_compliance(
    basis: str, status: str
) -> None:
    inputs = with_evidence(
        evaluation_inputs(),
        CaseEvidence(
            "pure-parser",
            (),
            replace(reviewed_selection(), basis=basis, reviewer=None),
            (replace(reviewed_behavior(), basis=basis, reviewer=None),),
        ),
    )

    report = evaluate(inputs)

    assert report.cases[0].selection.status == status
    assert report.cases[0].behavior[0].status == status


def test_evaluate_when_behavior_review_is_unknown_reports_inconclusive() -> None:
    inputs = with_evidence(
        evaluation_inputs(),
        CaseEvidence(
            "pure-parser", (), None, (replace(reviewed_behavior(), outcome="unknown"),)
        ),
    )

    report = evaluate(inputs)

    assert report.cases[0].behavior[0].status == "inconclusive"


@pytest.mark.parametrize("field", ["case_set_sha256", "source_snapshot_sha256"])
def test_evaluate_when_evidence_versions_are_stale_rejects_before_saving(
    field: str,
) -> None:
    inputs = with_evidence(
        evaluation_inputs(), CaseEvidence("pure-parser", (), None, ())
    )
    inputs = replace(inputs, evidence=replace(inputs.evidence, **{field: "stale-hash"}))
    sink = MemorySink()

    with pytest.raises(EvaluationError, match="version mismatch"):
        EvaluateSkills(MemorySource(inputs), sink)(created_at="2026-01-01T00:00:00Z")

    assert sink.reports == []


@pytest.mark.parametrize("problem", ["duplicate-case", "unknown-skill", "stale-quote"])
def test_evaluate_when_expectations_are_invalid_rejects_input(problem: str) -> None:
    inputs = evaluation_inputs()
    case = inputs.case_set.cases[0]
    if problem == "duplicate-case":
        cases = (case, case)
    elif problem == "unknown-skill":
        cases = (replace(case, required_skills=("nonexistent-skill",)),)
    else:
        cases = (replace(case, source_refs=(SourceRef(SKILL_PATH, "Outdated quote"),)),)
    inputs = replace(inputs, case_set=replace(inputs.case_set, cases=cases))

    with pytest.raises(EvaluationError):
        evaluate(inputs)


@pytest.mark.parametrize(
    "problem",
    [
        "duplicate-case",
        "unknown-case",
        "duplicate-check",
        "unknown-check",
        "unknown-read",
    ],
)
def test_evaluate_when_evidence_targets_are_invalid_rejects_input(problem: str) -> None:
    check = reviewed_behavior()
    entry = CaseEvidence("pure-parser", (), None, (check,))
    inputs = with_evidence(evaluation_inputs(), entry)
    if problem == "duplicate-case":
        cases = (entry, entry)
    elif problem == "unknown-case":
        cases = (replace(entry, case_id="missing-case"),)
    elif problem == "duplicate-check":
        cases = (replace(entry, checks=(check, check)),)
    elif problem == "unknown-check":
        cases = (
            replace(entry, checks=(replace(check, requirement_id="missing-check"),)),
        )
    else:
        cases = (replace(entry, reads=(ReadObservation("missing-skill", CITATION),)),)
    inputs = replace(inputs, evidence=replace(inputs.evidence, cases=cases))

    with pytest.raises(EvaluationError):
        evaluate(inputs)


@pytest.mark.parametrize(
    "problem",
    ["missing-reviewer", "missing-citation", "stale-citation", "missing-rationale"],
)
def test_evaluate_when_claim_has_no_review_provenance_rejects_input(
    problem: str,
) -> None:
    check = reviewed_behavior()
    if problem == "missing-reviewer":
        check = replace(check, reviewer=" ")
    elif problem == "missing-citation":
        check = replace(check, evidence=())
    elif problem == "stale-citation":
        check = replace(
            check, evidence=(Citation("review-artifact", "Not in artifact"),)
        )
    else:
        check = replace(check, rationale=" ")
    inputs = with_evidence(
        evaluation_inputs(), CaseEvidence("pure-parser", (), None, (check,))
    )

    with pytest.raises(EvaluationError):
        evaluate(inputs)


@pytest.mark.parametrize(
    ("example", "status"),
    [
        ("```bash\npytest tests/unit\n```", "static_inconsistency"),
        ("```sh\n$ pytest tests/unit\n```", "static_inconsistency"),
        ("```bash\nuv run pytest tests/unit\n```", "static_check_clear"),
        ("Use `pytest` for unit tests.", "static_check_clear"),
        ("```text\npytest is the test framework\n```", "static_check_clear"),
        ("```python\npytest.main()\n```", "static_check_clear"),
    ],
    ids=["bare-shell", "shell-prompt", "uv-shell", "prose", "text-fence", "python"],
)
def test_static_check_when_scanning_commands_only_flags_bare_shell_invocations(
    example: str, status: str
) -> None:
    inputs = evaluation_inputs(skill_content=f"{SOURCE_QUOTE}\n{example}\n")

    report = evaluate(inputs)

    finding = next(
        f for f in report.static_findings if f.subject == "backend-unit-testing"
    )
    assert finding.status == status
    if status == "static_inconsistency":
        assert "behavior unverified" in finding.explanation
        assert finding.evidence[-1] == Citation("AGENTS.md", UV_RULE)


def test_static_check_when_project_uv_rule_is_absent_reports_not_checked() -> None:
    inputs = evaluation_inputs(skill_content=f"{SOURCE_QUOTE}\n```bash\npytest\n```")
    inputs = replace(
        inputs, sources=tuple(s for s in inputs.sources if s.path != "AGENTS.md")
    )

    report = evaluate(inputs)

    assert [f.status for f in report.static_findings] == ["not_checked"]


@pytest.mark.parametrize("origin", ["bundle", "artifact"])
def test_evaluate_when_human_review_cites_illustration_cannot_promote_it_to_compliance(
    origin: str,
) -> None:
    inputs = with_evidence(
        evaluation_inputs(),
        CaseEvidence("pure-parser", (), reviewed_selection(), (reviewed_behavior(),)),
    )
    if origin == "bundle":
        bundle = replace(inputs.evidence, provenance="illustrative")
    else:
        bundle = replace(
            inputs.evidence,
            artifacts=(
                replace(inputs.evidence.artifacts[0], provenance="illustrative"),
            ),
        )

    report = evaluate(replace(inputs, evidence=bundle))

    assert report.cases[0].selection.status == "illustrative_only"
    assert report.cases[0].behavior[0].status == "illustrative_only"


@pytest.mark.parametrize("field", ["runtime", "model", "environment", "invocation"])
def test_evaluate_when_review_context_is_missing_reports_inconclusive(
    field: str,
) -> None:
    inputs = with_evidence(
        evaluation_inputs(),
        CaseEvidence("pure-parser", (), reviewed_selection(), (reviewed_behavior(),)),
    )
    context = replace(inputs.evidence.context, **{field: "not-recorded"})
    inputs = replace(inputs, evidence=replace(inputs.evidence, context=context))

    report = evaluate(inputs)

    assert report.cases[0].selection.status == "inconclusive"
    assert report.cases[0].behavior[0].status == "inconclusive"


def test_evaluate_when_project_revision_differs_rejects_stale_context() -> None:
    inputs = with_evidence(
        evaluation_inputs(), CaseEvidence("pure-parser", (), None, ())
    )
    context = replace(inputs.evidence.context, workspace_revision="different-revision")
    inputs = replace(inputs, evidence=replace(inputs.evidence, context=context))

    with pytest.raises(EvaluationError, match="project revision mismatch"):
        evaluate(inputs)


def test_evaluate_when_artifact_snapshot_is_missing_rejects_incomplete_capture() -> (
    None
):
    inputs = with_evidence(
        evaluation_inputs(), CaseEvidence("pure-parser", (), None, ())
    )

    with pytest.raises(EvaluationError, match="Missing artifact snapshot"):
        evaluate(replace(inputs, artifacts=()))
