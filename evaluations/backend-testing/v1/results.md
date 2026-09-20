# Pilot demonstration results

These are results from exercising the evaluator, not results from an agent
using the skills. The case set contains 10 authored scenarios and 36 observable
behavior requirements. Expectations are derived from the actual project files.

| Run | Static text check | Selection | Behavior |
| --- | --- | --- | --- |
| Actual project files | Two bare pytest command inconsistencies; E2E command check clear | 10 missing evidence | 36 missing evidence |
| Candidate source copy | All three narrow command checks clear | 10 missing evidence | 36 missing evidence |
| Explicit illustrative inputs | Same two baseline inconsistencies | 2 illustrative, 8 missing | 3 illustrative, 33 missing |

The [sample report](sample-report.md) is the real baseline CLI output. The
candidate changes only the two commands in [the proposed patch](candidate-uv-commands.patch),
applied to a disposable copy of captured instruction sources. It is a static
comparison, not a full runnable project or comparative agent run. The user's
actual skills remain unchanged. Baseline versions and rationale are recorded
in [candidate.md](candidate.md).

Candidate SHA-256 versions:

- Unit: `f8186b1f3297a16415df7e7faf3f05d09d66f22a397711df1660cc9e147e3ff4`
- Integration: `c3e2f6b69cda1a983ee7d31f0d3f90693a14e12f547b91ccb6ba6a76004f2492`
- E2E: unchanged, `a2ff6225e082165cb59df173b2d56d0a863deb846593f4095cf2b7b2fc4fa8d6`

The [illustrative input](illustrative-evidence.json) and its
[handwritten artifact](illustrative-artifacts.txt) demonstrate three separate
situations: relevant unit/architecture guidance together, a contrary real-file
test left in the unit suite despite supplied successful reads, and an
unsupported installed-wheel self-report. Their origin remains illustrative in
every result. They prove evaluator handling only; no agent was invoked.

The original local reports, full source snapshots, and input artifacts are
preserved under `.evaluation-runs/backend-testing-v1/{baseline,candidate,illustrative}`
in the implementation workspace. That directory is ignored because future
reports can contain private execution artifacts. A clone can regenerate a
baseline using the README command.

## Replay the illustration after a new commit

The supplied example is bound to its original case, source, and project
revision. A new commit correctly makes its old context stale. For this
**handwritten illustration only**, use a new baseline template to regenerate
its bindings. Never use this operation to rebind a real reviewed run.

First create `/tmp/skillscope-pilot-baseline` with the README command. Then:

```bash
uv run python - <<'PY'
import json
import shutil
from pathlib import Path

source = Path("evaluations/backend-testing/v1")
example = json.loads((source / "illustrative-evidence.json").read_text())
template = json.loads(Path("/tmp/skillscope-pilot-baseline/evidence-template.json").read_text())
assert example["provenance"] == "illustrative"
for key in ("case_set_sha256", "source_snapshot_sha256"):
    example[key] = template[key]
example["context"]["workspace_revision"] = template["context"]["workspace_revision"]
destination = Path("/tmp/skillscope-pilot-illustration-input")
destination.mkdir(exist_ok=False)
shutil.copyfile(source / "illustrative-artifacts.txt", destination / "illustrative-artifacts.txt")
(destination / "review.json").write_text(json.dumps(example, indent=2) + "\n")
PY
uv run skillscope evaluate \
  --project . \
  --cases evaluations/backend-testing/v1/cases.json \
  --evidence /tmp/skillscope-pilot-illustration-input/review.json \
  --output /tmp/skillscope-pilot-illustration-report
```

## Implementation verification

Both required Ruff checks pass. The full `uv run pytest` run collected 197
tests: 194 passed and three Docker E2E tests failed because the Docker daemon
refused the connection. This includes the new installed-wheel evaluation
test; its behavior remains unverified until Docker is available. The wheel
build succeeded. The 56 focused unit/integration evaluation tests passed.

Real source analysis and CLI report generation were exercised on the three
actual skills. Behavior improvement, autonomous skill routing, and actual
agent adherence remain unverified. The [capture procedure](../../../docs/09-skill-evaluation-pilot.md)
describes the next controlled experiment without automatically launching it.
