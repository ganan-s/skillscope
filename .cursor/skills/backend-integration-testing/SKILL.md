---
name: backend-integration-testing
description: Enforces Skillscope's pytest integration-test conventions for the Python backend. Use when testing SQLite repositories and migrations, Cursor transcript and hook adapters, FastAPI routes, CLI wiring, composition roots, filesystem fixtures, or code under tests/integration.
---

# Backend integration testing

Apply these conventions to Skillscope backend integration tests. Also apply
`backend-hexagonal-architecture` when a test exposes or changes an architectural
boundary.

## Role in the testing pyramid

Integration tests form the middle of the test pyramid. They prove that two or
more real Skillscope components honor their shared contract.

An integration test may use:

- real SQLite connections and production migrations;
- real temporary files and directories;
- sanitized Cursor transcript and hook-spool fixtures;
- the FastAPI application through an in-process test client;
- the real composition root with test configuration; and
- an in-process CLI runner.

An integration test must not use:

- the user's actual home directory, Cursor data, hooks, or Skillscope database;
- internet or external service access;
- a separately running backend process;
- a browser;
- arbitrary timing waits; or
- test-order dependencies.

Workflows requiring an installed application, real process boundaries, or a
browser belong in the end-to-end suite.

## Framework and location

Use `pytest`.

Place tests under `tests/integration/`, organized by boundary:

```text
tests/integration/
  api/
  cli/
  composition/
  plugins/
    cursor/
  storage/
  fixtures/
    cursor/
```

Name files `test_<boundary>.py`. Name tests:

```text
test_<operation>_<condition>_<observable_outcome>
```

Prefer test functions. Group scenarios in classes only when that improves
navigation; do not use test-class inheritance.

## What to integration test

Prioritize contracts that unit tests deliberately replace with ports or
in-memory values:

- ordered SQL migrations against an empty and previously migrated database;
- SQLite repository reads, writes, transactions, constraints, and row mapping;
- read-only serve connections and write rejection;
- Cursor transcript discovery and parsing from filesystem fixtures;
- Cursor hook-spool parsing and merge precedence;
- application use cases with real SQLite adapters;
- FastAPI routing, validation, error mapping, OpenAPI, and JSON serialization;
- production dependency wiring with test configuration;
- CLI option parsing and exit behavior; and
- compiled frontend mount/fallback behavior when frontend assets exist.

Do not duplicate pure domain cases already covered by unit tests. Exercise the
integration seam and its important failure modes.

## Test boundaries

Each test must state which real boundary it proves. Common scopes are:

### Storage adapter

Use the real connection factory, migrations, repositories, and explicit SQL.
The application service may be real when transaction ownership is part of the
contract.

### Cursor adapter

Use real fixture files and the real Cursor plugin. Inject the transcript root,
hook-spool path, platform, and clock. Never scan `~/.cursor`.

### REST API

Build the real FastAPI application with real query services and a temporary
snapshot database. Use an in-process client. Do not mock route handlers or
FastAPI internals.

### CLI

Invoke the real command registration and composition through an in-process CLI
runner with explicit temporary paths. Use a subprocess only when process
behavior itself is the requirement; otherwise reserve that for end-to-end.

### Composition

Construct the application from production wiring with test configuration and
replace only boundaries outside the scope of the test.

## Database conventions

Create databases under `tmp_path`. Never use an in-memory SQLite database when
the behavior depends on:

- WAL;
- read-only URI mode;
- multiple connections;
- locking;
- filesystem permissions; or
- persistence across application instances.

Apply production migrations rather than creating tables directly in test code.

Default to a fresh database per test. A broader fixture scope is allowed only
for immutable migrated templates copied into each test.

Tests must cover:

- migration from an empty store;
- repeated migration as a no-op;
- rejection of unsupported newer schemas;
- foreign-key enforcement;
- complete aggregate replacement in one transaction;
- rollback without partial child rows;
- unchanged revision idempotency;
- stale revision protection;
- deterministic list/detail ordering; and
- read-only serving that cannot create, migrate, or mutate the store.

Assert through repository or query-port results. Direct SQL assertions are
appropriate only when verifying schema, constraints, or atomicity that the
public port cannot expose.

## Cursor fixture conventions

Store only synthetic or sanitized native fixtures under
`tests/integration/fixtures/cursor/`.

Include focused fixtures for:

- a closed transcript with no skills;
- a successful `postToolUse` read of exact `SKILL.md`;
- repeated successful activations;
- `postToolUseFailure`;
- an offline read request with unknown outcome;
- malformed or truncated JSONL;
- an active or grace-period transcript;
- a continued conversation revision;
- missing and malformed frontmatter;
- resource reads before and after activation; and
- Linux and macOS path examples.

Fixtures must not contain real prompts, emails, access tokens, home paths, model
thoughts, or unrelated tool output.

Keep raw native shapes in fixtures. Do not pre-normalize them into the expected
canonical DTO, or the test will bypass the adapter behavior it claims to prove.

## Filesystem isolation

All writable paths come from `tmp_path` or an explicit test configuration.
Tests may copy read-only fixture trees into that temporary root.

Never depend on:

- the repository's current working directory unless that is the tested input;
- files created by another test;
- platform-specific `/tmp` contents;
- environment variables from the developer's shell; or
- absolute paths outside the test sandbox.

Use `monkeypatch` only to set a process boundary that production code genuinely
reads, such as a documented environment variable. Prefer passing explicit
configuration.

## FastAPI contract tests

Use the real application factory and an in-process test client.

Verify:

- `/api/v1/conversations` ordering, pagination, and empty skill lists;
- `/api/v1/conversations/{id}` task/load ordering and unknown-id response;
- `/api/v1/meta` API and schema compatibility fields;
- stable error bodies and status codes;
- Pydantic serialization of timestamps, enums, and optional values;
- API routes remain read-only;
- unknown `/api/...` paths return API `404`, not SPA HTML; and
- non-API routes use the frontend fallback only when assets are configured.

Seed data through the real write-side repository or a test data builder that
uses public storage ports. Do not insert ad hoc rows that violate production
invariants unless the test specifically verifies corruption handling.

## Test doubles

Use real implementations on both sides of the integration boundary.

Replace only dependencies outside that boundary:

- a fixed clock;
- deterministic ID generation;
- a platform detector;
- an external scheduler; or
- frontend assets not relevant to an API test.

Do not mock SQLite, FastAPI, filesystem calls, or the Cursor adapter in a test
claiming to integrate them.

Use narrow fakes that implement application ports. Avoid patching module
internals.

## Assertions

Assert behavior visible at the boundary:

- canonical snapshots and diagnostics from a plugin;
- persisted/queryable aggregates from repositories;
- transaction outcomes;
- HTTP status, headers, and JSON bodies;
- CLI exit codes and user-facing output; and
- files deliberately produced by the operation.

Do not assert internal helper calls or private object graphs.

When comparing large structures, prefer explicit expected DTOs or focused
golden JSON files. Review golden changes as API changes; never update them
blindly.

## Determinism and concurrency

Inject fixed UTC times and stable IDs. Control source mtimes explicitly when
testing quiescence or revision ordering.

Never use `sleep` to wait for:

- filesystem timestamp changes;
- grace periods;
- SQLite locks; or
- background work.

Drive clocks and synchronization explicitly. For lock tests, coordinate known
connection states and use bounded timeouts.

Tests may run in parallel. Each test owns its database, transcript root, hook
spool, and environment overrides.

## Failure-path requirements

Cover failures where adapters translate infrastructure behavior into the
application contract:

- unreadable or malformed native source;
- failed/denied read evidence;
- unavailable post-read snapshot;
- database busy/constraint failures;
- migration checksum mismatch;
- missing or incompatible store on serve;
- repository rollback; and
- invalid API query/path parameters.

Assert stable application errors or diagnostic codes. Do not expose raw SQL,
personal paths, or native payloads in expected REST errors.

## Running the suite

The canonical command is:

```bash
pytest tests/integration
```

Integration tests may take longer than unit tests but must remain suitable for
every pull request. They must run without network access, Cursor installation,
user hooks, external services, or a pre-existing database.

## Review checklist

- The test proves a real boundary between concrete components.
- It belongs in integration rather than unit or end-to-end.
- Production migrations, parsers, repositories, routes, or wiring are used.
- All state is isolated under temporary paths.
- No personal Cursor data or machine configuration is consulted.
- Real implementations are used inside the declared boundary.
- Mocks or fakes exist only outside that boundary.
- Assertions target public contracts and durable outcomes.
- Time, IDs, paths, and ordering are deterministic.
- Important rollback, malformed-input, and read-only cases are covered.
- The test passes alone, in parallel, and in any suite order.
