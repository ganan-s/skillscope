---
name: backend-hexagonal-architecture
description: Enforces Skillscope's hexagonal Python backend architecture. Use when creating, modifying, or reviewing backend domain models, application services, ports, FastAPI routes, CLI commands, SQLite repositories, harness plugins, composition wiring, or other code under src/skillscope.
---

# Backend hexagonal architecture

Apply these requirements to Skillscope backend work. Read
`docs/02-backend-architecture.md` and `docs/03-ingestion-contract.md` when a
change touches their contracts.

## Dependency rule

Dependencies point toward the application core:

```text
driving adapters -> application -> domain
driven adapters  -> application ports
composition root -> all concrete adapters
```

The domain and application layers never import FastAPI, `sqlite3`, Cursor
formats, filesystem discovery, CLI frameworks, or frontend code.

## Layers

### Domain

Place harness-neutral business concepts in `skillscope.domain`:

- conversation snapshots;
- canonical ingestion events;
- skill activations and resource reads;
- source revisions, readiness, evidence, and diagnostics; and
- invariants that do not depend on transport or persistence.

Use immutable dataclasses or similarly plain Python types. Domain types must not
be database rows, Pydantic HTTP schemas, or native Cursor payloads.

### Application

Place use cases and ports in `skillscope.application`.

Driving ports express product operations:

- ingest ready conversation snapshots;
- list conversations;
- get one conversation; and
- read store metadata.

Driven ports describe capabilities required by those use cases:

- discover and parse harness conversations;
- persist conversation aggregates transactionally;
- query conversation projections;
- inspect schema/store metadata; and
- obtain time or filesystem configuration only when determinism requires a
  port.

Define ports with `typing.Protocol` or abstract base classes. Use cases depend
on ports and domain types, never concrete adapters.

Application services own orchestration and transaction boundaries. They do not
parse Cursor JSONL, write SQL, construct HTTP responses, or read live skill
files.

### Driving adapters

Driving adapters translate external requests into application use cases:

- CLI commands;
- FastAPI routes; and
- a future scheduler or worker.

Routes validate and map REST DTOs, invoke one use case, and map its result.
Routes must not call repositories, issue SQL, invoke harness plugins, or read
the filesystem.

CLI commands parse options, invoke use cases, and render results. They contain
no ingest, database, or HTTP business logic.

### Driven adapters

Driven adapters implement application ports:

- the Cursor harness adapter owns transcript roots, hook spools, native parsing,
  and conversion to the canonical ingestion contract;
- SQLite adapters own connections, migrations, explicit SQL, row mapping, and
  read/write enforcement; and
- compiled frontend hosting is an HTTP delivery concern, not an application
  use case.

Native Cursor shapes stop at the Cursor adapter. SQLite row shapes stop at the
storage adapter. Neither may leak into application or domain APIs.

### Composition root

Keep concrete construction in an explicit composition root such as
`skillscope.bootstrap`.

The composition root selects configuration, creates concrete adapters, injects
them into use cases, and supplies those use cases to CLI or FastAPI adapters.
Do not instantiate SQLite repositories or Cursor plugins inside use cases or
routes.

## Required boundaries

### Ingest and serve

Preserve the write/read split:

- `skillscope ingest` may discover harness data, migrate SQLite, and write
  snapshots.
- `skillscope serve` opens SQLite read-only and may only execute query ports.

Do not let API routes trigger ingest, migrations, transcript discovery, or
filesystem snapshots.

### Harness ingestion contract

Treat `HarnessPlugin` as a driven port. A plugin:

1. discovers native conversations;
2. determines revision-scoped ingest eligibility;
3. merges native evidence sources;
4. emits one complete canonical conversation snapshot plus diagnostics; and
5. performs no database writes.

Only confirmed successful native evidence produces `skill.activated`.
Harness-specific tool names, fields, paths, and evidence rules remain inside
the adapter.

### REST contract

Pydantic request and response models belong to the API adapter. Convert them to
application input/output models at the route boundary.

The public REST contract must not expose:

- SQLite column or row structures;
- Cursor-native records;
- internal repository objects; or
- live filesystem behavior.

## Transactions and idempotency

The ingest use case defines one transaction per conversation aggregate.
Repository adapters implement that transaction atomically.

Re-ingesting an unchanged source revision is a no-op. Re-ingesting a continued
conversation replaces stale child snapshots. Do not scatter commits across
parsers or repositories.

## Error mapping

Define domain/application errors independently of transports:

- not found;
- incompatible store;
- invalid canonical snapshot;
- deferred or rejected native source; and
- persistence conflict/failure.

Driving adapters map these errors to CLI exit behavior or REST responses.
Driven adapters translate native exceptions before crossing their port.

Do not expose SQL errors, raw hook payloads, or internal filesystem details
through the REST API.

## Implementation workflow

For each backend change:

1. Identify the use case and domain behavior.
2. Change domain types or invariants only if the product concept changed.
3. Define or adjust the smallest necessary port.
4. Implement behavior against the port in the application layer.
5. Implement transport or infrastructure details in an adapter.
6. Wire the concrete adapter only in the composition root.
7. Verify import direction and the ingest/serve read-write boundary.

Do not create an interface for internal helpers that have no adapter boundary.
Hexagonal architecture is for dependency control, not class proliferation.

## Review checklist

- Domain and application code are framework- and storage-independent.
- FastAPI routes call use cases, not repositories or plugins.
- CLI commands call use cases, not implementation helpers.
- Cursor parsing and native evidence stay inside the Cursor adapter.
- SQL and row mapping stay inside SQLite adapters.
- Concrete implementations are selected only in the composition root.
- Ingest owns writes; serve remains read-only.
- Transactions wrap complete conversation aggregates.
- Public DTOs do not leak adapter-specific shapes.
- New abstractions represent real ports rather than unnecessary indirection.
