# 8. Observational skill effectiveness

## Status

This document extends the [vision](01-vision.md), the
[ingestion contract](03-ingestion-contract.md), and the
[API resource design](05-api-resource-design.md). It defines the first product
slice for assessing skill effectiveness.

The slice is **observational**. It persists and projects evidence an author can
use to judge a skill. It does not score skills, critique them, rewrite them, or
aggregate them across conversations.

## Decision

v1 already answers “which `SKILL.md` files were loaded?” Effectiveness needs
two more kinds of evidence:

1. **Native observations the current event model drops**, especially confirmed
   failed `SKILL.md` loads and the success/error close of a turn.
2. **Derived observations computed at read time** from events already stored in
   one conversation snapshot.

Judgment stays with the author. The dashboard may show these signals; it must
not label a skill as good, bad, followed, or ignored.

## Why load events are not enough

`skill.activated` is a confirmed successful exact `SKILL.md` read. That is a
load observation, not an effectiveness observation.

From activations alone, the product cannot tell whether:

- the agent tried a skill and the read failed;
- the agent later read another file from that skill directory;
- the user sent a follow-up after the load;
- the same skill was loaded more than once in the thread; or
- the containing turn later ended in success or error.

Failed `SKILL.md` reads currently exist only as ingest diagnostics. Diagnostics
are not public API resources, so authors cannot inspect them. Transcript
`turn_ended` records are parsed for session shape but are not stored.

## What this slice will not do

The following remain out of scope:

- numeric scores, grades, or “effectiveness” percentages;
- LLM or heuristic judging of whether the agent followed the skill;
- cross-conversation catalogs, rollups, or leaderboards;
- write-back, critique, or suggested skill edits;
- treating unknown-outcome transcript Reads as failures;
- promoting non-`SKILL.md` failed reads into public resources;
- copying native error messages into canonical events or the REST API.

Unknown outcome stays a diagnostic. Confirmed failure of an exact `SKILL.md` is
a first-class event. Those two must not be collapsed.

## Canonical events

The contract remains additive. `CONTRACT_VERSION` stays `1`. Existing snapshots
without the new events remain valid; derived observations then report the
honest unknown/false defaults.

The SQLite events table already stores `event_type` plus a JSON payload. This
slice does not require a schema migration.

### `skill.activation_failed`

Represents one confirmed unsuccessful attempt to read an exact `SKILL.md`.

An adapter emits this event only when:

1. native evidence confirms failure, timeout, denial, or interruption;
2. the native operation semantically reads or activates one file;
3. the target is a concrete path with no glob characters; and
4. its case-sensitive basename is exactly `SKILL.md`.

Fields:

- concrete path string;
- source bucket;
- native tool-use id when available;
- turn identity and sequence;
- optional observed time; and
- canonical `reason`: `failed`, `denied`, `timeout`, `interrupted`, or
  `unknown`.

This event is never an activation. It cannot parent a `skill.resource_read`.
Failed reads of other files, globs, and unknown-outcome requests remain
diagnostics only.

The ingest diagnostic `read_failed` is retained for operator troubleshooting.
The public product observation is this event, not the diagnostic.

### `turn.completed`

Represents the native close of one conversation turn.

Fields:

- optional turn index;
- canonical `status`: `success`, `error`, or `unknown`.

For Cursor v1 this comes from transcript `type: turn_ended`. A turn close is
not a conversation close and does not replace `session.closed`.

If the transcript has no `turn_ended` record for a turn, no event is emitted
and later projections report `containing_turn_status: unknown`.

## Derived observations

Derived observations are a **read-model projection**, not stored events. The
SQLite read adapter computes them from canonical events in the same snapshot.
They are not inferred by the Cursor parser and must not be written back during
ingest.

Each public skill activation carries an `observations` object:

| Field | True / value when |
|---|---|
| `resource_follow_through` | this activation has at least one nested resource read |
| `repeated_in_conversation` | another `skill.activated` in this conversation has the same path |
| `followed_by_user_task` | a later `task.recorded` exists (`turn_index` greater than this activation) |
| `containing_turn_status` | matching `turn.completed` status, else `unknown` |

These flags describe stored evidence, not skill quality:

- resource follow-through means another file under the skill directory was
  read, not that the agent complied with the manifest;
- a later user task means the thread continued, not that the skill helped;
- a successful turn status is the harness turn close, not a product score;
- missing evidence is `false` or `unknown`, never guessed true.

If `turn_index` is missing, `followed_by_user_task` is `false` and
`containing_turn_status` is `unknown`.

## Public API

Conversation summary gains:

- `load_failure_count`: number of `skill.activation_failed` events in the
  snapshot.

Conversation detail gains:

- `skill_load_failures`: ordered failed exact `SKILL.md` attempts.

Each load failure contains:

- `id`, `path`, `source`, `reason`, `turn_index`, `sequence`, `failed_at`,
  `time_provenance`.

Each skill activation gains required `observations` as specified above.
Failed attempts never appear in `skill_activations`.

The public API still does not expose diagnostics, native error text, or raw
canonical events.

## Cursor mapping

| Native evidence | Canonical result |
|---|---|
| `postToolUse` exact `SKILL.md` | `skill.activated` (unchanged) |
| `postToolUseFailure` exact `SKILL.md` | `skill.activation_failed` plus `read_failed` diagnostic |
| `postToolUseFailure` of any other path | `read_failed` diagnostic only |
| transcript `Read` with no hook outcome | `read_outcome_unknown` diagnostic only |
| transcript `turn_ended` | `turn.completed` |
| hook `sessionEnd` | `session.closed` (unchanged) |

The Cursor adapter maps native failure fields to canonical `reason` and drops
`error_message`. Native `is_interrupt` becomes `interrupted`. Timeout-like and
permission-like `failure_type` values become `timeout` and `denied`. Any other
confirmed unsuccessful outcome becomes `failed`.

`generation_id` still joins a failed load or activation to a user turn.

## Frontend

The thread inspector may show observations in plain language next to a
confirmed load. Failed loads appear on the timeline as failed attempts, not as
activations. Labels must describe evidence (“later prompt recorded”, “resource
file read”) rather than verdicts (“skill worked”, “agent ignored the skill”).

## Later work

A later document may introduce cross-conversation skill views or author-facing
summaries. Those summaries must still be built from these observations, not
from a hidden score. Numeric grading, LLM critique, and write-back remain
out of scope until explicitly designed.
