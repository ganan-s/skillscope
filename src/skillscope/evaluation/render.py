"""Human-readable evaluation report rendering, with no numeric quality score."""

from collections import Counter

from skillscope.domain.evaluation import EvaluationReport, Finding


def _finding(finding: Finding) -> list[str]:
    lines = [f"- **{finding.subject}: {finding.status}** — {finding.explanation}"]
    lines.extend(
        f"  - Evidence `{ref.artifact_id}`: {ref.quote!r}" for ref in finding.evidence
    )
    return lines


def render_markdown(report: EvaluationReport) -> str:
    spec = report.inputs.case_set
    lines = [
        f"# Skillscope evaluation: {spec.id} {spec.version}",
        "",
        f"Created: {report.created_at}",
        "",
        "This is a project-specific evaluation record, not a skill quality score.",
        f"Expectation provenance: {spec.provenance.note}",
        "",
        "## Preserved context",
        "",
        f"- Case set SHA-256: `{report.inputs.case_set_snapshot.sha256}`",
        f"- Source manifest SHA-256: `{report.inputs.source_snapshot_sha256}`",
        f"- Project revision: `{report.inputs.project_revision}`",
        f"- Working-tree status entries: {len(report.inputs.project_dirty_paths)} "
        "(recorded in JSON; non-source project files are not snapshotted).",
        "- Full input specifications, source contents, evidence and cited artifact "
        "contents are preserved in `report.json`.",
    ]
    if report.inputs.evidence:
        bundle = report.inputs.evidence
        lines.extend(
            [
                f"- Supplied evidence run: `{bundle.run_id}`",
                f"- Bundle provenance: **{bundle.provenance}** "
                "(preserved for every finding).",
                "- Artifact provenance: "
                + ", ".join(f"{a.id}: {a.provenance}" for a in bundle.artifacts),
                f"- Runtime/model: {bundle.context.runtime} / {bundle.context.model}",
                f"- Supplied environment: {bundle.context.environment}",
                f"- Supplied invocation: {bundle.context.invocation}",
            ]
        )
    else:
        lines.append(
            "- No agent execution evidence supplied; behavior remains unverified."
        )
    lines.extend(["", "## Static command consistency", ""])
    for finding in report.static_findings:
        lines.extend(_finding(finding))
    lines.extend(["", "## Per-skill findings", ""])
    for skill in spec.skills:
        affected = [case for case in spec.cases if skill.id in case.required_skills]
        results = [
            result
            for result in report.cases
            if result.case_id in {c.id for c in affected}
        ]
        counts = Counter(
            f.status for result in results for f in (result.selection, *result.behavior)
        )
        snapshot = next(
            source for source in report.inputs.sources if source.path == skill.path
        )
        lines.extend(
            [
                f"### {skill.id}",
                "",
                f"Version SHA-256: `{snapshot.sha256}`",
                f"Required in: {', '.join(c.id for c in affected) or 'no cases'}.",
                f"Finding counts (not a score): {dict(counts)}. "
                "Shared-case findings may appear under more than one skill; "
                "they do not establish individual causality.",
                "",
            ]
        )
    lines.extend(["## Per-case evidence", ""])
    by_id = {case.id: case for case in spec.cases}
    for result in report.cases:
        case = by_id[result.case_id]
        expected = ", ".join(case.required_skills) or "none required"
        reads = ", ".join(r.skill_id for r in result.observed_reads) or "none"
        lines.extend(
            [
                f"### {case.id}: {case.title}",
                "",
                case.task,
                "",
                f"Expected applicability: {expected}.",
                f"Selection rationale: {case.selection_rationale}",
                f"Supplied read observations: {reads} (not a compliance judgment).",
                "",
            ]
        )
        lines.extend(_finding(result.selection))
        requirements = {req.id: req.description for req in case.requirements}
        for finding in result.behavior:
            lines.append(f"- Check: {requirements[finding.subject]}")
            lines.extend(_finding(finding))
        lines.append("")
    lines.extend(["## Limits and next step", ""])
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    lines.extend(
        [
            "",
            "Capture a case in an isolated workspace, preserve the execution log and "
            "produced artifacts, and fill `evidence-template.json` with cited reviews. "
            "Run `skillscope evaluate` again with `--evidence` "
            "and a new output directory. For a proposed revision, "
            "generate a new template against the candidate files "
            "and repeat the same cases/settings; do not reuse baseline evidence.",
            "",
        ]
    )
    return "\n".join(lines)
