# Candidate revision: align the canonical test commands

The supplied patch changes two examples, without changing the live skills:

- Unit skill: `pytest tests/unit` becomes `uv run pytest tests/unit`.
- Integration skill: `pytest tests/integration` becomes
  `uv run pytest tests/integration`.

This is a static consistency finding. `AGENTS.md` explicitly requires uv for
Python commands and already lists both uv invocations. The E2E skill also uses
`uv run pytest tests/e2e`. The statements “Use `pytest`” in the skills specify a
test framework and are compatible with uv; they do not need changing.

The finding was derived from these starting file versions (SHA-256):

| Source | SHA-256 |
| --- | --- |
| `AGENTS.md` | `c77e679cd7f815b604496283a88202a342f37619549a0e5d94594ac936614df4` |
| `.cursor/skills/backend-unit-testing/SKILL.md` | `736e36c3db7e9c83c59bd37b5e8a23964c2c3b38d46a68106751fcae8094f75f` |
| `.cursor/skills/backend-integration-testing/SKILL.md` | `b375a056b267b0df9b4f4b9bbdc805ff59364789bcd512e93e06392f8790985d` |
| `.cursor/skills/backend-e2e-testing/SKILL.md` | `a2ff6225e082165cb59df173b2d56d0a863deb846593f4095cf2b7b2fc4fa8d6` |

The candidate aims to remove competing command examples when an agent follows
the unit or integration skill. It does not establish that an agent previously
ran the wrong command, that the revised wording changes selection, or that
outcomes improve. Those claims remain unverified until comparable runs supply
execution evidence and an independent review.

The targeted behavior requirement is `commands_use_uv` in
`unit-native-record-memory`, `unit-application-port`,
`boundary-jsonl-fixture`, `integration-sqlite-rollback`,
`integration-fastapi-client`, and `integration-cli-runner`. Unchanged E2E and
classification cases provide useful controls. A run should preserve the exact
skill content, case version, project revision/worktree context, harness/model
settings, and evidence provenance for each side of a comparison.

Use a disposable copy or worktree to apply `candidate-uv-commands.patch` for a
candidate run. Execute the same authored task against baseline and candidate
instructions with matching runtime settings. Capture actual commands, their
outputs and exit status, produced diffs/artifacts, and the runtime's native
skill-read evidence when available. Review task applicability separately from
read events; an extra skill read is not proof of wrong selection. Review the
observable requirements against the artifacts rather than accepting an agent's
self-report. A static before/after finding supports command consistency only.
