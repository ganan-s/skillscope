# 9. Backend testing skill-evaluation pilot

## Purpose and scope

This pilot helps maintain Skillscope's project-specific testing skills before
there is a known failed conversation. It evaluates proposed task expectations
for `backend-unit-testing`, `backend-integration-testing`, and
`backend-e2e-testing`, preserves the evaluated inputs, and explains findings a
skill author can review.

This is an explicit expansion of the original observation-only scope in the
[vision](01-vision.md). It leaves conversation ingest, snapshot history, and
read-only serving intact. The interface is a local CLI and readable report;
there is no model dependency, paid runner, new HTTP endpoint, or dashboard
requirement. The pilot does not rewrite skills or produce a health score.

The case set is project-specific. Its expectations come from the existing
skill bodies and shared `AGENTS.md` instructions, not historical agent failures.
The versioned cases live in
[`evaluations/backend-testing/v1/cases.json`](../evaluations/backend-testing/v1/cases.json).
Review the case expectations when the project requirements change; adding more
skill files or narrowing their descriptions is not automatically an improvement.

## Run the pilot

From the repository root, run:

```bash
uv run skillscope evaluate \
  --project . \
  --cases evaluations/backend-testing/v1/cases.json \
  --output /tmp/skillscope-pilot-baseline
```

Use a fresh output directory for every report. The command produces:

| File | Purpose |
|---|---|
| `report.md` | Readable per-case and per-skill findings, evidence limits, and proposed revision rationale |
| `report.json` | Structured findings plus preserved case, source, context, and supplied evidence records |
| `evidence-template.json` | A review input bound to the evaluated case set and source versions |

The first run needs only the actual project files. It can confirm a static
text finding and show the applicable-skill expectations and behavior checks.
Selection and behavior without reviewed evidence remain unverified. Successful
report generation means the evaluation operation completed, not that the skills
passed or agent behavior improved.

After collecting and reviewing artifacts, copy and complete the generated
template, then run:

```bash
uv run skillscope evaluate \
  --project . \
  --cases evaluations/backend-testing/v1/cases.json \
  --evidence /path/to/review.json \
  --output /tmp/skillscope-pilot-reviewed
```

Do not substitute illustrative artifacts or an agent's self-report for an
observed run. Inputs explicitly marked illustrative or self-reported remain
unsupported as behavior evidence, even when they contain plausible claims.

## What the cases check

The case specification contains readable tasks, applicable skill expectations,
observable requirements, and provenance. Boundary and negative cases matter as
much as straightforward matches:

| Task boundary | Intended testing guidance | Evidence a reviewer needs |
|---|---|---|
| In-memory parsing, domain rules, or application behavior through fakes | Unit testing | Produced test code and execution record; no test filesystem, database, network, process, clock, or environment I/O |
| Real fixture files, SQLite, in-process FastAPI, or in-process CLI wiring | Integration testing | Real components at the declared boundary, isolated temporary state, production wiring where relevant |
| Installed wheel, separate process, real socket, or browser | E2E testing | Packaging/process setup and public assertions, synthetic data, Testcontainers when the scenario needs it |
| A task outside backend testing | No required testing skill merely because its words overlap | A review of task applicability, without penalizing unrelated legitimate skills |
| Work spanning more than one test layer or an architectural boundary | Multiple skills may apply | Separate explanation of each applicable boundary; no penalty for skill count |

Running `pytest` necessarily reads code and starts a process. The unit skill's
no-I/O requirement describes the test behavior being authored, not a ban on the
test runner reading files. Likewise, real SQLite or a TestClient alone does not
make a test E2E. Review these distinctions in the resulting artifacts, not by
matching isolated keywords in a command log.

The current project `AGENTS.md` requires the architecture and all three testing
skills for backend work. Therefore, loading all four under that instruction is
not a selection failure. Forced reads also do not measure automatic skill
routing. This pilot can review which guidance is applicable to a case and how
the resulting work respects it. A future routing experiment would need an
explicitly controlled discovery policy, preserved as different experiment
context, before drawing conclusions about automatic selection.

## Evidence contract and trust

Use the generated template as the contract for review input. Its
`case_set_sha256` and `source_snapshot_sha256` bind judgments to the evaluated
case set and source snapshots. Keep those values unchanged when reviewing that
version. Generate a new template after changing the skill, AGENTS.md, or case
set; do not relabel an old review as evidence for a new version.

The template sets bundle `provenance` to `illustrative`, leaves runtime, model,
environment, and invocation pending, and copies the report's project revision
into `context.workspace_revision`. Change provenance to `supplied_capture`
only when supplying actual captured artifacts. Each artifact independently
requires `provenance`: `supplied_capture` or `illustrative`. An illustrative
bundle or any cited illustrative artifact keeps the finding `illustrative_only`,
even if a claim says `basis: human_review`.

Record the case, project revision, relevant uncommitted changes, runtime
version, chosen model and settings, prompt, and execution environment.
`workspace_revision` must match the evaluated report's project revision and
describe the original run's starting revision, not a later commit containing
its output. A revision mismatch rejects the input. For otherwise eligible
human reviews, any context field equal to `not-run`, `not-recorded`, `unknown`,
or `unavailable` makes the finding `inconclusive`. Keep genuinely unknown values
unknown rather than inventing context to obtain a reviewed result.

Each evidence case has `case_id`, `reads`, `selection`, and `checks`. A selection
may be `null`; checks can be omitted from the array when evidence is missing.
Each read entry has `skill_id` and one `evidence` citation containing
`artifact_id` and `quote`; it remains a supplied observation.
Every supplied selection or check requires a `basis` (`human_review`,
`illustrative`, or `agent_self_report`), a nonempty `rationale`, and an `evidence`
array of `{ "artifact_id": "...", "quote": "..." }` citations. Each quote must
be an exact nonempty substring of the named artifact. `human_review` also
requires a nonempty `reviewer`. A behavior check names its `requirement_id` and
records `outcome` as `met`, `not_met`, or `unknown`.

`selection.assessed_skills` records the applicable guidance demonstrated by
the agent's choices in this particular attempt. It is not the reviewer's ideal
answer copied from `required_skills`; that would make the comparison circular.
Explain the agent's actual boundary decision and cite its produced work or
substantive task response. Raw skill reads alone cannot substantiate this
assessment. `selection.complete` says the reviewer completed that scoped
assessment. It does not attest that tool capture is complete. An incomplete
assessment produces `inconclusive` for otherwise eligible human evidence.

Artifact paths are relative to the evidence JSON's directory and must stay
inside it; absolute paths, parent traversal, and escaping symlinks are rejected.
The current adapter accepts UTF-8 text inputs up to 2,000,000 bytes each,
preserving their contents and SHA-256 hashes. This includes produced source,
diffs, and text execution logs; binary artifacts need a supported text record
for this pilot. An excerpt match proves the cited text exists, not that the
text is true, the run is complete, or the reviewer is correct.

| Evidence kind | What the report may establish | What it cannot establish |
|---|---|---|
| Current skill/instruction text | A reproducible static finding about those captured bytes | Agent behavior or the effect of a proposed change |
| Supplied successful-read observation | The supplied record describes a read, with its stated provenance | Adherence, demonstrated applicability, complete selection coverage, or a missed/extra skill |
| Artifact-backed `human_review` | `reviewed_met` or `reviewed_not_met` for the cited expectation | Independently verified compliance or causal improvement |
| Agent self-report | `unsupported_self_report`: what the agent claimed | That it actually performed the claimed actions |
| Illustrative bundle, cited artifact, or review | `illustrative_only`: how the evaluator handles that input | A real agent outcome, including when a sample claim says `human_review` |
| Incomplete/unknown human review or pending run context | `inconclusive` | Failure or success |
| Missing review | `missing_evidence` | Failure or success |

These labels remain distinct in case and skill summaries. Raw supplied reads
do not automatically become a selection judgment. In particular, an absent
record is not proof that an agent missed a relevant skill, and additional
loaded skills are not automatically mistakes. A reviewer must consider the task
and capture limits; a complete negative claim needs evidence of the relevant
scope, not a small favorable excerpt.

The current Cursor parser confirms the literal native `Read` operation on an
exact `SKILL.md` path. The collector can snapshot other read-shaped payloads,
but a snapshot alone does not broaden the parser's confirmed activation rule.
It reads the filesystem after the successful operation to capture a manifest
snapshot; it does not preserve the exact returned tool body. Its
read/task/session fields do not capture the execution behavior needed for this
rubric. The existing
[observational signals](08-skill-effectiveness.md) therefore remain useful
context, not an adherence oracle.

### Illustrative JSON and a useful behavior review

The following is syntax guidance, not captured agent evidence. Start from the
generated template and copy its real hashes and project revision. Suppose an
explicitly illustrative `example-review.txt` contains this task response for
`boundary-testclient-not-e2e`:

```text
Place this test under tests/integration. FastAPI TestClient and SQLite run in
one process here; no installed wheel, separate process, real socket, or browser
is required. Keep the real FastAPI and SQLite boundary; do not mock it or add a
process just to keep the E2E label.
```

A compact evidence document for that illustrative artifact is:

```json
{
  "schema_version": 1,
  "run_id": "illustrative-review-syntax",
  "provenance": "illustrative",
  "case_set_sha256": "COPY_FROM_GENERATED_TEMPLATE",
  "source_snapshot_sha256": "COPY_FROM_GENERATED_TEMPLATE",
  "context": {
    "runtime": "not-run",
    "model": "not-run",
    "environment": "not-recorded",
    "invocation": "not-run",
    "workspace_revision": "COPY_FROM_GENERATED_TEMPLATE"
  },
  "artifacts": [{
    "id": "task-response",
    "path": "example-review.txt",
    "description": "Authored illustration of a review-only task response",
    "provenance": "illustrative"
  }],
  "cases": [{
    "case_id": "boundary-testclient-not-e2e",
    "reads": [],
    "selection": {
      "basis": "human_review",
      "assessed_skills": ["backend-integration-testing", "backend-e2e-testing"],
      "complete": true,
      "rationale": "The response uses the E2E boundary to classify the concrete TestClient/SQLite work as integration.",
      "reviewer": "Example reviewer (fictional)",
      "evidence": [{"artifact_id": "task-response", "quote": "Place this test under tests/integration."}]
    },
    "checks": [{
      "requirement_id": "integration_classification",
      "basis": "human_review",
      "outcome": "met",
      "rationale": "The response places the test in integration and explains which E2E boundaries are absent.",
      "reviewer": "Example reviewer (fictional)",
      "evidence": [{"artifact_id": "task-response", "quote": "no installed wheel, separate process, real socket, or browser\nis required."}]
    }]
  }]
}
```

This stays `illustrative_only` despite the sample claim's `human_review` basis.
For an actual captured review-only task response, a real reviewer could support
the same scoped selection and classification findings with `supplied_capture`
provenance, truthful complete context, and exact artifact excerpts. In this
case the substantive classification response is the requested deliverable;
it does not claim that a code change or test run happened. The unassessed
`preserve_real_boundary` requirement remains `missing_evidence` in the sample,
rather than being automatically credited from the surrounding prose.

A contrary example concerns `unit-native-record-memory`: if the actual diff
puts a test under `tests/unit` that writes a file under `tmp_path` or reads a
JSONL fixture from disk, a reviewer can mark `in_memory_inputs` as `not_met` and cite
the actual file-writing/reading code. A captured successful pytest exit would
not overturn that result; passing tests do not establish the required test
boundary. This would justify revisiting the skill's pure-input guidance or its
selection, independently of the static uv command finding.

If either attempt has only an incomplete Read log, leave `selection: null`
unless other artifacts support an assessment. If a reviewer has begun but
cannot complete it, use `complete: false`; otherwise eligible human evidence
then stays `inconclusive`. An empty or partial `reads` array never establishes
that a required skill was missed, and no entry in `assessed_skills` should be
added merely to match the expected list.

## Preserved versions and comparisons

`report.json` retains the full case specification, captured skill and shared
AGENTS.md/source text with SHA-256 hashes, supplied artifact contents and
hashes, and project context including git revision and dirty paths. This is an
evaluation snapshot separate from the conversation SQLite store. Reports can
be examined after the original project files change.

A git commit and dirty-path list do not recreate every byte of an uncommitted
workspace. Preserve the relevant source diff and produced artifacts for a
behavior comparison, in addition to the report's source snapshots. Runtime
metadata supplied by a reviewer is a statement of context, not independently
attested by the offline evaluator.

Compare runs only when the case set, task input, project starting state,
runtime/model/settings, and review rubric are controlled or their differences
are explicitly explained. Baseline and candidate skill hashes should differ
only for the intended revision. Review both reports and artifacts; there is no
aggregate score that turns a single outcome into a general claim of success.

## Small proposed revision

The current unit and integration skills call bare `pytest tests/unit` and
`pytest tests/integration` their canonical commands. Shared AGENTS.md requires
uv for Python commands. The smallest revision to test is:

```diff
-pytest tests/unit
+uv run pytest tests/unit

-pytest tests/integration
+uv run pytest tests/integration
```

This finding concerns executable command examples in the relevant project
scope. “Use pytest” still correctly names the test framework. `uv pip install`
in an isolated installed-wheel E2E setup also follows the uv requirement; the
word `pip` alone is not a conflict.

The proposed edit aligns the examples with the shared policy and reduces
contradictory guidance. The pilot leaves the actual skills unchanged. It does
not establish that any agent previously used the wrong command or that the
edit improves selection, adherence, task outcomes, or efficiency. Those
behavioral effects remain unverified until comparative review supports them.

## Concrete next step: collect a controlled run

Runtime availability was investigated with local `--help` and `--version`
commands, without reading personal transcripts or invoking a model. The local
Codex executable advertises `exec --json`, an explicit working directory and
sandbox mode; Cursor Agent advertises streaming JSON output. Availability of
those flags alone does not establish that a capture is complete or that an
account is ready. The pilot has no automatic runtime adapter.

For a deliberately initiated experiment:

1. Prepare two isolated copies at the same project revision: one baseline and
   one candidate with only the proposed skill edit. Include the same project
   instructions and required fixtures in both. Preserve any starting patch.
2. Put one case's task in a prompt file outside the copies. Keep its wording,
   model, settings, and environment identical for both runs. Do not insert the
   expected answer into the task. Record how the runtime discovers project
   instructions and skills; Codex and Cursor discovery behavior may differ.
3. Run the selected runtime against each copy, preserving its JSON event stream,
   process exit status, stderr, final diff, produced tests, and test output.
4. Inspect those artifacts independently against each requirement. Complete the
   corresponding baseline or candidate review template using exact excerpts.
5. Generate fresh reviewed reports and describe what the comparison supports
   and what remains uncertain. Repeat representative cases before generalizing.

For example, these commands illustrate a possible **future** Codex capture
after the isolated copies and prompt have been prepared. Replace the paths and
model deliberately. They initiate model work using the configured account;
`skillscope evaluate` never executes them, and they were not run for this
pilot's static demonstration.

```bash
codex --version > /tmp/skillscope-run-baseline/runtime-version.txt
codex exec --json --ephemeral --sandbox workspace-write \
  -C /tmp/skillscope-run-baseline/project \
  --model CHOSEN_MODEL \
  - < /tmp/skillscope-case.txt \
  > /tmp/skillscope-run-baseline/events.jsonl \
  2> /tmp/skillscope-run-baseline/stderr.txt
```

Capture the exit status immediately and collect the resulting diff and test
output. Repeat with the candidate copy and its own output paths. The example
assumes the run directories already exist and the project copy is a git
repository. Keep generated logs outside the agent's working tree. Do not treat
the final assistant message as a replacement for execution artifacts. If the
runtime does not expose a needed observation, mark that requirement unknown or
explain the limit in the human review.

## Verification and current limits

The implementation's tests verify the evaluator's rules and adapter boundaries:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest
```

The full suite includes installed-wheel E2E tests and needs a working
Docker-compatible runtime. A missing daemon is an environment blocker, not a
passing or silently skipped E2E result. Unit/integration fixtures prove product
behavior of the evaluator, not behavior of an agent using the three skills.

The real-file run checks actual skill and AGENTS.md text and writes the report.
Illustrative fixtures exercise evidence handling. No comparative agent run or
behavioral improvement is implied by either result. The first useful outcome is
a reviewable case set, versioned inputs, honest unknowns, and a narrow revision
whose purpose can be tested.

Evaluation reports and supplied artifacts may contain project instructions,
code, prompts, and execution output. They remain local, but should be reviewed
before sharing or committing them. The evaluator reads only explicitly supplied
project and evidence inputs; no user transcript is needed to start.
