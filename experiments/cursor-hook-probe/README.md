# Cursor hook ingestion probe

This experiment tests which skill-read facts Cursor can provide to a harness
plugin. It informed the canonical ingestion contract in
[`docs/03-ingestion-contract.md`](../../docs/03-ingestion-contract.md).

## Result

Tested with Cursor 3.21.13 on Linux:

- Offline agent transcript JSONL includes assistant `tool_use` requests but not
  tool results. A failed read and a successful read therefore look the same
  offline.
- A successful file read emits `postToolUse`; a failed, timed-out, or denied
  read emits `postToolUseFailure`.
- Hook payloads include stable conversation, generation, and tool-use ids,
  workspace roots, transcript path, tool input, and Cursor version.
- For `Read`, the successful `tool_output` is a JSON string containing the path
  and returned content length. It does not contain the returned file body.
- A success hook can immediately snapshot the file from disk. That is a
  sufficiently contemporaneous v1 snapshot; Skillscope does not require
  byte-for-byte proof of the exact tool response.
- Cursor's hook input uses `tool_input.file_path`; the offline transcript
  observed by this experiment used `input.path`. That native difference stays
  inside the Cursor adapter.

These findings rule out treating an offline `Read` request as a confirmed
`skill.activated` event.

## Contents

- `capture.py` is a fail-open command hook that appends raw hook envelopes to a
  local JSONL spool. For successful, concrete `SKILL.md` reads it also captures
  a contemporaneous body and SHA-256 hash.
- `hooks.example.json` is the project-local hook configuration used by the
  probe. It is not installed automatically.
- `fixtures/captured/` contains minimized, sanitized records derived from the
  observed Cursor payloads.
- `fixtures/probe-skill/SKILL.md` is a benign skill body for manual tests.

The raw spool is `experiments/cursor-hook-probe/.local/events.jsonl` and is
gitignored because it can contain user prompts, email addresses, absolute
paths, and skill contents.

## Run manually

1. Copy `hooks.example.json` to `.cursor/hooks.json`.
2. Confirm the hooks appear in Cursor's Hooks settings.
3. Start a new project conversation to exercise `sessionStart`.
4. Submit a prompt to exercise `beforeSubmitPrompt`.
5. Read an existing concrete `SKILL.md` and a missing `SKILL.md`.
6. End the conversation to exercise `sessionEnd`.
7. Inspect `.local/events.jsonl`.
8. Remove `.cursor/hooks.json` when finished.

The hook is observational and fails open. It prints an empty JSON object and
does not inject context or alter tool results.

## Limits of this proof

This run directly captured successful and failed read events. The shapes for
`sessionStart`, `beforeSubmitPrompt`, and `sessionEnd` are based on Cursor's
documented common hook schema and remain to be preserved as live fixtures from
a fresh conversation.

The probe does not establish that hooks existed in older Cursor versions or
that every Cursor surface emits identical events.
