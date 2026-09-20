"""Real CLI composition, JSON validation, file capture, and report persistence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from skillscope.cli import main

pytestmark = pytest.mark.integration

SKILL_PATH = ".cursor/skills/backend-unit-testing/SKILL.md"
SOURCE_QUOTE = "Unit tests use in-memory inputs."
UV_RULE = "Use uv for Python environments, dependencies, and commands."


def write_json(path: Path, contents: dict) -> None:
    path.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")


def case_document() -> dict:
    ref = {"path": SKILL_PATH, "quote": SOURCE_QUOTE}
    return {
        "schema_version": 1,
        "id": "synthetic-cli-pilot",
        "version": "1.0",
        "provenance": {
            "kind": "project_specification",
            "note": "Synthetic integration fixture, not an agent outcome.",
        },
        "skills": [{"id": "backend-unit-testing", "path": SKILL_PATH}],
        "cases": [
            {
                "id": "pure-parser",
                "title": "Pure parser test",
                "task": "Test parsing with in-memory records.",
                "required_skills": ["backend-unit-testing"],
                "allowed_skills": [],
                "forbidden_skills": [],
                "requirements": [
                    {
                        "id": "no-io",
                        "description": "Keep parser test inputs in memory.",
                        "source_refs": [ref],
                    }
                ],
                "selection_rationale": "The task exercises pure parsing.",
                "source_refs": [ref],
            }
        ],
    }


@pytest.fixture
def pilot_files(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    skill = project / SKILL_PATH
    skill.parent.mkdir(parents=True)
    skill.write_bytes(
        (
            f"{SOURCE_QUOTE}\r\nSynthetic café example.\r\n"
            "```bash\r\npytest tests/unit\r\n```\r\n"
        ).encode()
    )
    (project / "AGENTS.md").write_text(UV_RULE + "\n", encoding="utf-8")
    cases = tmp_path / "cases.json"
    write_json(cases, case_document())
    return project, cases


def evaluate(
    project: Path, cases: Path, output: Path, evidence: Path | None = None
) -> int:
    arguments = [
        "evaluate",
        "--project",
        str(project),
        "--cases",
        str(cases),
        "--output",
        str(output),
    ]
    if evidence:
        arguments.extend(["--evidence", str(evidence)])
    return main(arguments)


def evidence_from_template(
    project: Path, cases: Path, tmp_path: Path
) -> tuple[dict, Path]:
    baseline = tmp_path / "baseline"
    assert evaluate(project, cases, baseline) == 0
    evidence = json.loads((baseline / "evidence-template.json").read_text())
    evidence["run_id"] = "synthetic-cli-review"
    evidence["provenance"] = "illustrative"
    evidence["context"] = {
        "runtime": "synthetic fixture",
        "model": "none",
        "environment": "isolated test files",
        "invocation": "no agent invoked",
        "workspace_revision": evidence["context"]["workspace_revision"],
    }
    return evidence, tmp_path / "evidence.json"


def test_evaluate_when_files_are_valid_preserves_exact_snapshots_and_unknown_behavior(
    pilot_files: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project, cases = pilot_files
    output = tmp_path / "report"
    source_bytes = (project / SKILL_PATH).read_bytes()
    case_bytes = cases.read_bytes()

    exit_code = evaluate(project, cases, output)

    assert exit_code == 0
    report = json.loads((output / "report.json").read_text())
    source = next(s for s in report["inputs"]["sources"] if s["path"] == SKILL_PATH)
    assert source["content"].encode() == source_bytes
    assert source["sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert (
        report["inputs"]["case_set_snapshot"]["sha256"]
        == hashlib.sha256(case_bytes).hexdigest()
    )
    assert report["cases"][0]["selection"]["status"] == "missing_evidence"
    assert report["cases"][0]["behavior"][0]["status"] == "missing_evidence"
    assert report["static_findings"][0]["status"] == "static_inconsistency"
    assert (project / SKILL_PATH).read_bytes() == source_bytes
    template = json.loads((output / "evidence-template.json").read_text())
    assert (
        template["source_snapshot_sha256"] == report["inputs"]["source_snapshot_sha256"]
    )
    assert template["cases"][0]["selection"] is None
    markdown = (output / "report.md").read_text()
    assert "behavior remains unverified" in markdown
    assert "Pure parser test" in markdown
    assert "backend-unit-testing" in markdown
    assert "not a compliance pass" in capsys.readouterr().out


def test_evaluate_when_illustration_is_supplied_preserves_artifact_and_provenance(
    pilot_files: tuple[Path, Path], tmp_path: Path
) -> None:
    project, cases = pilot_files
    evidence, evidence_path = evidence_from_template(project, cases, tmp_path)
    artifact_bytes = b"Synthetic fixture: reviewer inspected in-memory inputs.\r\n"
    (tmp_path / "review.txt").write_bytes(artifact_bytes)
    evidence["artifacts"] = [
        {
            "id": "review",
            "path": "review.txt",
            "description": "Synthetic review artifact",
            "provenance": "illustrative",
        }
    ]
    citation = {"artifact_id": "review", "quote": "reviewer inspected in-memory inputs"}
    evidence["cases"][0].update(
        {
            "reads": [{"skill_id": "backend-unit-testing", "evidence": citation}],
            "selection": {
                "basis": "human_review",
                "assessed_skills": [
                    "backend-unit-testing",
                    "backend-hexagonal-architecture",
                ],
                "complete": True,
                "rationale": "Synthetic reviewed applicability assessment.",
                "reviewer": "Test reviewer",
                "evidence": [citation],
            },
            "checks": [
                {
                    "requirement_id": "no-io",
                    "basis": "human_review",
                    "outcome": "met",
                    "rationale": "Synthetic review of in-memory test inputs.",
                    "reviewer": "Test reviewer",
                    "evidence": [citation],
                }
            ],
        }
    )
    write_json(evidence_path, evidence)
    output = tmp_path / "reviewed"

    exit_code = evaluate(project, cases, output, evidence_path)

    assert exit_code == 0
    report = json.loads((output / "report.json").read_text())
    assert report["cases"][0]["selection"]["status"] == "illustrative_only"
    assert report["cases"][0]["behavior"][0]["status"] == "illustrative_only"
    artifact = report["inputs"]["artifacts"][0]
    assert artifact["content"].encode() == artifact_bytes
    assert artifact["sha256"] == hashlib.sha256(artifact_bytes).hexdigest()
    assert (
        report["inputs"]["evidence_snapshot"]["sha256"]
        == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    )
    assert "not independently verified" in (output / "report.md").read_text()


def test_evaluate_when_output_exists_rejects_without_overwriting_report(
    pilot_files: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project, cases = pilot_files
    output = tmp_path / "existing"
    output.mkdir()
    report_path = output / "report.json"
    report_path.write_text("existing report\n")

    exit_code = evaluate(project, cases, output)

    assert exit_code == 1
    assert report_path.read_text() == "existing report\n"
    assert sorted(p.name for p in output.iterdir()) == ["report.json"]
    assert "fresh report directory" in capsys.readouterr().err


def test_evaluate_when_skill_changes_rejects_old_evidence_and_keeps_baseline(
    pilot_files: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project, cases = pilot_files
    evidence, evidence_path = evidence_from_template(project, cases, tmp_path)
    write_json(evidence_path, evidence)
    baseline = (tmp_path / "baseline" / "report.json").read_bytes()
    skill = project / SKILL_PATH
    skill.write_bytes(skill.read_bytes() + b"\nRevised command guidance.\n")
    output = tmp_path / "stale"

    exit_code = evaluate(project, cases, output, evidence_path)

    assert exit_code == 1
    assert "version mismatch" in capsys.readouterr().err
    assert not output.exists()
    assert (tmp_path / "baseline" / "report.json").read_bytes() == baseline


@pytest.mark.parametrize("problem", ["extra-top-level", "extra-nested", "wrong-type"])
def test_evaluate_when_json_shape_is_invalid_reports_error_without_output(
    pilot_files: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    problem: str,
) -> None:
    project, cases = pilot_files
    document = case_document()
    if problem == "extra-top-level":
        document["unrecognized"] = "sensitive-input-value"
    elif problem == "extra-nested":
        document["cases"][0]["quality_score"] = "sensitive-input-value"
    else:
        document["cases"][0]["title"] = 123
    write_json(cases, document)
    output = tmp_path / "invalid"

    exit_code = evaluate(project, cases, output)

    assert exit_code == 1
    error = capsys.readouterr().err
    assert "Invalid evaluation JSON" in error
    assert "sensitive-input-value" not in error
    assert not output.exists()


def test_evaluate_when_source_quote_is_stale_reports_provenance_error(
    pilot_files: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project, cases = pilot_files
    document = case_document()
    document["cases"][0]["source_refs"][0]["quote"] = "No longer in source."
    write_json(cases, document)
    output = tmp_path / "stale-source"

    exit_code = evaluate(project, cases, output)

    assert exit_code == 1
    assert "Stale source quote" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("escape", ["parent", "absolute", "symlink"])
def test_evaluate_when_source_escapes_project_rejects_containment_violation(
    pilot_files: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    escape: str,
) -> None:
    project, cases = pilot_files
    outside = tmp_path / "outside.md"
    outside.write_text(SOURCE_QUOTE)
    if escape == "parent":
        path = "../outside.md"
    elif escape == "absolute":
        path = str(outside)
    else:
        (project / "linked.md").symlink_to(outside)
        path = "linked.md"
    document = case_document()
    document["skills"][0]["path"] = path
    write_json(cases, document)
    output = tmp_path / "escaped-source"

    exit_code = evaluate(project, cases, output)

    assert exit_code == 1
    assert "Cannot evaluate skills" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("escape", ["parent", "absolute", "symlink"])
def test_evaluate_when_artifact_escapes_evidence_root_rejects_containment_violation(
    pilot_files: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    escape: str,
) -> None:
    project, cases = pilot_files
    evidence, _ = evidence_from_template(project, cases, tmp_path)
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("Synthetic outside artifact.")
    if escape == "parent":
        path = "../outside.txt"
    elif escape == "absolute":
        path = str(outside)
    else:
        (evidence_root / "linked.txt").symlink_to(outside)
        path = "linked.txt"
    evidence["artifacts"] = [
        {
            "id": "outside",
            "path": path,
            "description": "Outside",
            "provenance": "illustrative",
        }
    ]
    evidence_path = evidence_root / "evidence.json"
    write_json(evidence_path, evidence)
    output = tmp_path / "escaped-artifact"

    exit_code = evaluate(project, cases, output, evidence_path)

    assert exit_code == 1
    assert "Cannot evaluate skills" in capsys.readouterr().err
    assert not output.exists()


def test_evaluate_when_source_is_not_utf8_reports_input_error_without_output(
    pilot_files: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project, cases = pilot_files
    (project / SKILL_PATH).write_bytes(b"\xff\xfe invalid UTF-8")
    output = tmp_path / "invalid-encoding"

    exit_code = evaluate(project, cases, output)

    assert exit_code == 1
    assert "UnicodeDecodeError" in capsys.readouterr().err
    assert not output.exists()


def test_evaluate_when_using_project_pilot_checks_actual_three_skill_sources(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[3]
    cases = repository / "evaluations/backend-testing/v1/cases.json"
    document = json.loads(cases.read_text())
    source_paths = {"AGENTS.md", *(skill["path"] for skill in document["skills"])}
    for case in document["cases"]:
        source_paths.update(ref["path"] for ref in case["source_refs"])
        source_paths.update(
            ref["path"]
            for requirement in case["requirements"]
            for ref in requirement["source_refs"]
        )
    project = tmp_path / "project"
    for relative in source_paths:
        destination = project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((repository / relative).read_bytes())
    output = tmp_path / "project-pilot"

    exit_code = evaluate(project, cases, output)

    assert exit_code == 0
    report = json.loads((output / "report.json").read_text())
    assert {skill["id"] for skill in report["inputs"]["case_set"]["skills"]} == {
        "backend-unit-testing",
        "backend-integration-testing",
        "backend-e2e-testing",
    }
    assert {case["case_id"] for case in report["cases"]} == {
        case["id"] for case in document["cases"]
    }
    assert all(
        finding["status"] == "missing_evidence"
        for case in report["cases"]
        for finding in (case["selection"], *case["behavior"])
    )
    assert report["inputs"]["evidence"] is None
