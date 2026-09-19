# 4. Cursor POC: harness + ingest

## Status

This document describes the v1 Cursor harness POC: a hook-based collector, a
Cursor adapter plugin, and `skillscope ingest` into SQLite. It is the handoff
for evaluation.

For why hooks are required, the production enablement steps, and how to test
Skillscope in a dev environment, see
[hooks and running ingest](07-hooks-and-dev-ingest.md).

## Quick start

### 1. Install

```bash
uv sync
```

### 2. Configure Cursor hooks

Copy the example hooks configuration into your project's `.cursor/` directory:

```bash
cp examples/cursor/hooks.json .cursor/hooks.json
```

Confirm the hooks appear in Cursor Settings > Hooks. The collector runs as a
fail-open subprocess: it prints `{}` and never injects context into the agent.

**Privacy:** The spool file may contain prompts, workspace paths, and skill
contents. It is gitignored by default. The collector sanitises email, model,
and unrelated tool output before spooling.

### 3. Run conversations

Use Cursor normally. The hooks observe `sessionStart`, `beforeSubmitPrompt`,
`postToolUse` (successful reads), `postToolUseFailure`, and `sessionEnd`.

### 4. Ingest

```bash
# Ingest using default paths (discovers from ~/.cursor/projects)
skillscope ingest --harness cursor

# Ingest with explicit paths (useful for testing/evaluation)
skillscope ingest --harness cursor \
  --transcripts path/to/transcripts \
  --spool path/to/hooks.jsonl \
  --db path/to/output.sqlite \
  --grace-seconds 0
```

The command prints a summary: `inserted=N, updated=N, unchanged=N, skipped=N,
deferred=N, failed=N`.

### 5. Query the database

```bash
# List conversations
sqlite3 db.sqlite "SELECT native_conversation_id, title, readiness_basis FROM conversations;"

# Count events by type
sqlite3 db.sqlite "SELECT event_type, COUNT(*) FROM events GROUP BY event_type;"

# List skill activations with metadata
sqlite3 db.sqlite "
  SELECT e.event_id, e.occurred_at,
         json_extract(e.payload, '$.path') AS skill_path,
         json_extract(e.payload, '$.skill_name') AS skill_name,
         json_extract(e.payload, '$.source_bucket') AS source_bucket
  FROM events e
  WHERE e.event_type = 'skill.activated'
  ORDER BY e.sequence;
"

# List user tasks
sqlite3 db.sqlite "
  SELECT e.event_id, json_extract(e.payload, '$.raw_text') AS task_text
  FROM events e
  WHERE e.event_type = 'task.recorded'
  ORDER BY e.sequence;
"

# Diagnostics
sqlite3 db.sqlite "SELECT code, message, path FROM diagnostics;"
```

## Activation rules

A `skill.activated` event is emitted only when all of these hold:

1. A Cursor `postToolUse` hook confirms the read succeeded.
2. The tool is `Read` or `ReadFile`.
3. The target is a concrete path (no glob characters).
4. The case-sensitive basename is exactly `SKILL.md`.

Offline transcript `Read` requests produce a `read_outcome_unknown` diagnostic,
never an activation. Failed reads produce a `read_failed` diagnostic.

## Schema overview

```
conversations
  id, harness_id, native_conversation_id, contract_version,
  source_revision, source_updated_at, readiness_basis,
  title, workspace_paths, started_at, ended_at

events
  id, conversation_id (FK), contract_version, event_id, event_type,
  harness_id, native_conversation_id, sequence, native_turn_id,
  turn_index, occurred_at, time_provenance, evidence (JSON), payload (JSON)

diagnostics
  id, conversation_id (FK), code, message, path, record_position
```

Event types: `session.closed`, `task.recorded`, `skill.activated`.

## Portability boundary

All Cursor-specific code lives in:

- `src/skillscope/plugins/cursor/` (collector, paths, parser, plugin)
- `examples/cursor/hooks.json`

The canonical contract (`domain/models.py`, `plugins/base.py`), storage, and
CLI are IDE-neutral. A future IDE adapter implements the `HarnessPlugin`
protocol and emits the same `ConversationSnapshot` events. No changes to
ingest, storage, or the eventual dashboard.

## Privacy

- The hook spool is stored locally and gitignored.
- The collector strips `user_email`, `model`, and `tool_output` before spooling.
- The SQLite database contains prompts and skill contents. Treat it as
  sensitive.
- `skillscope serve` binds only to `127.0.0.1`.
