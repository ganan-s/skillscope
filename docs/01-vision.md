# 1. Vision: skill load visibility

**v1 is a localhost web dashboard of closed conversations and the `SKILL.md` files they actually loaded.** It does not score skills, rewrite them, or re-read the filesystem at display time. Per-conversation observational signals for skill effectiveness are specified in [skill effectiveness](08-skill-effectiveness.md).

## Problem

Agent harnesses load `SKILL.md` files with almost no visibility for the author. After a chat ends, it is hard to answer:

- Which conversations loaded skills at all?
- Which skill files were read, in what order, from which source?
- What did those files contain *then*, not what they contain now?

v1 exists to make that history inspectable. Judgment stays with the author.

## Product (narrow)

The main entrypoint is a **localhost conversation list**. Drill-down is **one thread → the skill files loaded in that conversation**.

Display is fed only by data written at ingest time. If the project was deleted, the skill was edited, or the machine layout changed, the dashboard still shows what was loaded then.

Default project name: **skillscope**. Local only: a Python backend, SQLite, a
read-only REST API, and a separately built frontend.

| Command | Role |
|---|---|
| `skillscope ingest` | Discovers closed sessions, parses them, writes the snapshot store |
| `skillscope serve` | Reads **only** that store; never opens workspaces or re-scans skill dirs |

No cloud. Conversation transcripts and skill snapshots stay on the machine.

### Visualization is a localhost web app

v1’s dashboard is `skillscope serve`: a read-only REST API and a bundled
frontend, served together on localhost and backed only by SQLite. The frontend
framework is a separate decision and does not change the backend boundary.
Running serve and opening that URL **is** the product. It is not a gap to fill
with an in-editor panel.

It is **not**:

- A Cursor marketplace plugin (those package skills, MCP, hooks, rules, and commands for the **agent**; they do not render author-facing panels)
- A VS Code / Cursor extension webview inside the workbench

One UI serves every harness. A later Claude (or other) ingest plugin must not require a second dashboard. An optional later wrapper that merely opens this same localhost app is allowed; do not ship two UIs in v1.

**Harness plugin** vs **Cursor marketplace plugin** are different words. In this project, “plugin” means the ingest adapter (`cursor` in v1) that finds transcripts and emits canonical events. It does not mean a marketplace bundle or an IDE extension.

## Native unit: the conversation thread

A row in the list is a finished conversation: title, when, workspace path string, and skill-name chips taken from snapshots.

The thread page shows stored user queries and ordered skill loads (name, path, source, time, repeats). Paths are informational; live file links are not required.

A closed thread with **zero** unambiguous skill loads still appears, labeled **No skills loaded**. That absence is a real observation, not a reason to hide the thread.

## What v1 will not do

Out of scope until a later doc:

- Open or in-flight sessions
- A resident background ingest worker or live transcript watcher
- Aggregates, critique, scores, or write-back
- Additional harness plugins beyond Cursor
- Re-reading skill files or repos when serving the UI
- Cursor-native visualization (marketplace plugin, MCP-in-chat query as the dashboard, IDE webview)
- First-class Windows QA (include Windows in the Cursor harness plugin only if `~/.cursor/projects` works unchanged)

## Principles that define v1

These are product constraints, not implementation trivia. Later docs will specify schema and APIs; they should not contradict this section.

### 1. The store is a snapshot, not a live index

Ingest writes everything the UI needs. Serve does not open workspaces, does not read `SKILL.md` from disk, and does not re-scan `~/.cursor/skills`.

If a repo moves or a skill file changes tomorrow, yesterday’s thread still shows yesterday’s path, name, and description.

### 2. Harness and OS details live in a harness plugin

Path conventions, transcript formats, and “is this session closed?” rules differ by harness and OS. They do **not** belong in the dashboard or in SQLite as first-class product concepts.

The core app never hardcodes `~/.cursor`. It asks a **harness plugin** where to look and how to parse. v1 ships one harness plugin: `cursor`.

A later harness is another ingest plugin that emits the same canonical events. The localhost UI does not change.

### 3. Only closed sessions become truth

Ingest finished conversations only. Skip in-progress agent runs so partial JSONL and mid-turn tool calls do not appear as complete history.

Do not ingest a thread that is still growing. If the user continues a chat later, ingest again when it is closed; upsert by conversation id.

Cursor's offline transcript records read requests but not their results. v1
therefore uses an opt-in, fail-open Cursor hook collector to spool successful
and failed read evidence. The hook does not write SQLite; periodic
`skillscope ingest` merges its spool with the closed transcript.

### 4. A skill load is an unambiguous `SKILL.md` file read

Activation is a **skill file read**, not “the path contains `skill`.”

Count `skill.activated` only when all of these hold:

- Native evidence confirms that the operation succeeded; a recorded request
  with unknown outcome is not an activation
- The tool is a file read (Cursor `Read`), not grep, glob, list, edit, or shell (`cat`, `sed`, …)
- The target is a file, not a directory
- The basename is exactly `SKILL.md` (not `SKILLS.md`, `skill.md`, `SKILL.mdx`)
- The path is a concrete file path (no glob characters)
- If the evidence includes a payload snapshot, it parses as YAML frontmatter
  with a `name` field; if the payload is missing, still record the path but
  mark it unavailable so the UI can show uncertainty rather than inventing a
  skill

Resource reads (other files in the same skill directory) are optional and must be tied to an already-identified skill dir from a valid `SKILL.md` activation **in that thread**.

Negative cases that must **not** count as activation: `SKILLS.md`, `.mdc` rules, `CLAUDE.md`, `rg SKILL.md`, `Glob **/SKILL.md`, `Read` of a skill `reference.md` without a `SKILL.md` read, shell `cat`.

## How the pieces fit

```mermaid
flowchart LR
  osDetect[OS auto-detect]
  plugin[Cursor harness plugin]
  hook[Cursor hook spool]
  closed[Closed sessions only]
  parse[Unambiguous SKILL.md parser]
  db[(Snapshot SQLite)]
  serve[skillscope serve]
  api[Read-only REST API]
  web[Bundled frontend]
  list[Conversation list]
  detail[Thread: skills loaded]
  osDetect --> plugin
  hook --> plugin
  plugin --> closed
  closed --> parse
  parse --> db
  db --> serve
  serve --> api
  serve --> web
  api --> web
  web --> list
  list --> detail
```

1. Runtime OS selects transcript roots **inside the harness plugin**.
2. The plugin yields **closed** sessions only.
3. The parser emits canonical events and denormalized snapshots.
4. SQLite holds those snapshots.
5. `skillscope serve` reads only that store, exposes the read-only API, and
   hosts the built frontend that renders the two localhost screens.

## Canonical events

The harness plugin produces events; ingest stores them as snapshots.

| Event | Meaning |
|---|---|
| `session.closed` | Finished conversation ready to ingest |
| `task.recorded` | User message text copied into the store |
| `skill.activated` | Unambiguous `SKILL.md` read, with snapshot fields |
| `skill.activation_failed` | Confirmed unsuccessful exact `SKILL.md` read |
| `turn.completed` | Native close of one turn (`success` / `error` / `unknown`) |
| `skill.resource_read` | Optional extra file under that skill dir; snapshot path + name |

## What ingest must freeze

Enough to render the two screens without touching git or the original skill tree later.

**Conversation:** id, harness id, title, workspace path **string**, started/ended timestamps, raw user-query texts.

**Each skill load:** path string; skill name and description from payload frontmatter when present; source bucket inferred from the **path string at ingest** (`user`, `cursor-builtin`, `agents`, `project`, `unknown`); turn index; timestamp; repeat-safe identity; `payload_missing` flag; enough of the file body (or a hash plus frontmatter) to show what was loaded.

Source buckets and OS path layouts are inferred by the plugin at ingest. They are stored as data on the row. The dashboard does not re-derive them from the live machine.

## Privacy

v1 is local-only. Ingest copies user query text and skill file snapshots into SQLite on the same machine. Serve binds to localhost and does not upload that store. Treat the database as sensitive: it can contain prompts and skill contents that never belonged in a shared log.

## Later docs

This file is the product vision. Follow-on docs should cover, without expanding v1 scope:

- Harness plugin contract (Cursor: OS roots, closed-session rule, parser)
- Snapshot schema
- The frontend implementation for the two-screen localhost dashboard
