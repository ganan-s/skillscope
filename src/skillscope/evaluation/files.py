"""Explicit local JSON inputs and immutable report directories."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from skillscope.domain.evaluation import (
    CaseSet,
    EvaluationError,
    EvaluationInputs,
    EvaluationReport,
    EvidenceBundle,
    TextSnapshot,
)
from skillscope.evaluation.render import render_markdown

MAX_INPUT_BYTES = 2_000_000


class _CaseDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contents: CaseSet


class _EvidenceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contents: EvidenceBundle


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot(path: Path, label: str) -> TextSnapshot:
    with path.open("rb") as handle:
        data = handle.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise EvaluationError(f"Input exceeds {MAX_INPUT_BYTES} bytes: {label}")
    return TextSnapshot(label, _digest(data), data.decode("utf-8"))


def _within(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise EvaluationError(f"Expected a relative contained file path: {name}")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise EvaluationError(f"File escapes the input root: {name}")
    return resolved


def _git(project: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


class FileEvaluationSource:
    def __init__(self, project: Path, cases: Path, evidence: Path | None) -> None:
        self.project = project.resolve()
        self.cases = cases
        self.evidence = evidence

    def load(self) -> EvaluationInputs:
        try:
            case_snapshot = _snapshot(self.cases, self.cases.name)
            spec = _CaseDocument.model_validate_json(
                '{"contents":' + case_snapshot.content + "}"
            ).contents
            paths = {"AGENTS.md", *(s.path for s in spec.skills)}
            for case in spec.cases:
                paths.update(ref.path for ref in case.source_refs)
                paths.update(
                    ref.path for req in case.requirements for ref in req.source_refs
                )
            sources = tuple(
                _snapshot(_within(self.project, path), path) for path in sorted(paths)
            )
            manifest = json.dumps(
                {s.path: s.sha256 for s in sources},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            evidence_snapshot = None
            bundle = None
            artifacts = ()
            if self.evidence:
                evidence_snapshot = _snapshot(self.evidence, self.evidence.name)
                bundle = _EvidenceDocument.model_validate_json(
                    '{"contents":' + evidence_snapshot.content + "}"
                ).contents
                artifacts = tuple(
                    _snapshot(_within(self.evidence.parent, a.path), a.path)
                    for a in bundle.artifacts
                )
            return EvaluationInputs(
                case_set=spec,
                case_set_snapshot=case_snapshot,
                sources=sources,
                source_snapshot_sha256=_digest(manifest),
                project_revision=_git(self.project, "rev-parse", "HEAD")
                or "unavailable",
                project_dirty_paths=tuple(
                    _git(self.project, "status", "--porcelain").splitlines()
                ),
                evidence=bundle,
                evidence_snapshot=evidence_snapshot,
                artifacts=artifacts,
            )
        except ValidationError as exc:
            # Do not echo potentially sensitive input values from validation errors.
            errors = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['type']}"
                for e in exc.errors()
            )
            raise EvaluationError(f"Invalid evaluation JSON: {errors}") from exc
        except (OSError, UnicodeError) as exc:
            raise EvaluationError(
                f"Cannot read evaluation input: {type(exc).__name__}"
            ) from exc


class FileEvaluationSink:
    def __init__(self, output: Path) -> None:
        self.output = output

    def save(self, report: EvaluationReport) -> None:
        template = {
            "schema_version": 1,
            "run_id": "replace-with-captured-run-id",
            "provenance": "illustrative",
            "case_set_sha256": report.inputs.case_set_snapshot.sha256,
            "source_snapshot_sha256": report.inputs.source_snapshot_sha256,
            "context": {
                "runtime": "not-run",
                "model": "not-run",
                "environment": "not-recorded",
                "invocation": "not-run",
                "workspace_revision": report.inputs.project_revision,
            },
            "artifacts": [],
            "cases": [
                {"case_id": case.id, "reads": [], "selection": None, "checks": []}
                for case in report.inputs.case_set.cases
            ],
        }
        try:
            # Never update an old report or overwrite a user-selected directory.
            self.output.mkdir(parents=True, exist_ok=False)
            (self.output / "report.json").write_text(
                json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (self.output / "report.md").write_text(
                render_markdown(report), encoding="utf-8"
            )
            (self.output / "evidence-template.json").write_text(
                json.dumps(template, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            raise EvaluationError(
                f"Cannot create fresh report directory: {type(exc).__name__}"
            ) from exc
