# Local golden-session ingest harness

This experiment captures one real Cursor conversation on a developer machine,
sanitizes it into a golden pack, and replays ingest against that pack.

Production hooks, why they are required, and the manual `skillscope ingest`
dev loop are documented in
[`docs/07-hooks-and-dev-ingest.md`](../../docs/07-hooks-and-dev-ingest.md).
This directory is only the diverted-spool golden replay.

It is local-only. The golden copy is gitignored. Default `uv run pytest` does
not collect these tests. Containerized E2E under `tests/e2e/` is a separate
suite.

The production collector in `src/skillscope/plugins/cursor/collector.py` is the
spool writer. This directory only wraps it, sanitizes the capture, and replays
the result.

## Capture a conversation

`generate_golden.py` only sanitizes a capture. It does not talk to Cursor, so
running it before a hooked session fails with a missing spool.

1. Install project hooks:

   ```bash
   uv run python experiments/cursor-golden-session/generate_golden.py --install-hooks
   ```

2. Confirm the hooks appear in Cursor Settings > Hooks.
3. Start a **new** project conversation. An already-open chat will not emit
   `sessionStart`.
4. Submit a prompt that causes the agent to:
   - read `experiments/cursor-golden-session/fixtures/probe-skill/SKILL.md` twice;
   - read `experiments/cursor-golden-session/fixtures/missing/SKILL.md` once.
5. End the conversation so `sessionEnd` fires.
6. Remove `.cursor/hooks.json` when finished.

Raw output is `experiments/cursor-golden-session/.local/raw-spool.jsonl`.
Treat it as sensitive.

## Generate the golden copy

After the capture exists:

```bash
uv run python experiments/cursor-golden-session/generate_golden.py
```

The generator:

- selects the latest captured conversation that includes `session_ended`;
- finds the matching `agent-transcripts` JSONL under `~/.cursor/projects`, or
  uses `--transcripts`;
- fails with a checklist if `session_started`, `task_submitted`, two
  `read_succeeded`, one `read_failed`, or `session_ended` is missing;
- writes a sanitized pack to `.local/golden/` with stable ids, placeholder
  paths, and placeholder prompt text.

Useful flags:

```bash
uv run python experiments/cursor-golden-session/generate_golden.py \
  --transcripts /path/to/conversation.jsonl \
  --conversation-id <native-id>
```

Re-running generate overwrites `.local/golden/`.

## Run the local replay tests

```bash
uv run pytest experiments/cursor-golden-session -m live
```

Or:

```bash
SKILLSCOPE_LIVE=1 uv run pytest experiments/cursor-golden-session -m live
```

The tests skip unless `-m live` (or `SKILLSCOPE_LIVE=1`) is set. They also skip
if `.local/golden/` has not been generated, with a pointer back to this README.

They replay `CursorPlugin` and in-process `skillscope ingest` against the golden
files only. They do not scan `~/.cursor`.

Generator unit tests do not need a live capture:

```bash
uv run pytest experiments/cursor-golden-session/test_generate_golden.py
```
