---
name: backend-unit-testing
description: Enforces Skillscope's pytest unit-test conventions for the Python backend. Use when creating, modifying, or reviewing unit tests, domain logic, application use cases, canonical event parsing, test doubles, fixtures, or code under tests/unit.
---

# Backend unit testing

Apply these conventions to Skillscope backend unit tests. Also apply
`backend-hexagonal-architecture` when the tested code changes architectural
boundaries.

## Role in the testing pyramid

Unit tests form the broad base of the test suite. They provide fast,
deterministic feedback about one unit of behavior without exercising
infrastructure.

A unit test:

- runs entirely in one Python process;
- performs no filesystem, SQLite, network, subprocess, clock, or environment
  I/O;
- does not start FastAPI or use its test client;
- does not load migrations or production configuration; and
- finishes independently of test execution order.

If a test needs a real database, filesystem, HTTP stack, composition root, or
multiple concrete adapters, it belongs in the integration or end-to-end suite.

## Framework and location

Use `pytest`.

Place tests under `tests/unit/`, mirroring the production package:

```text
tests/unit/
  domain/
  application/
  adapters/
```

Use `adapters/` only for pure adapter logic such as native-record normalization
or row/DTO mapping. Tests that open files, SQLite connections, or HTTP clients
are not unit tests.

Name files `test_<subject>.py`. Name tests:

```text
test_<behavior>_<condition>_<expected_outcome>
```

Prefer test functions. Use classes only to group related scenarios; do not use
test-class inheritance.

## What to unit test

Prioritize:

- domain invariants and value-object behavior;
- application use cases through their ports;
- ingest eligibility and canonical event classification;
- idempotency and replacement decisions expressed as pure logic;
- error translation at application boundaries;
- source-bucket and path classification;
- frontmatter and native-record normalization from in-memory values;
- deterministic DTO mapping; and
- every bug fix with a focused regression test.

Do not unit-test trivial dataclass construction, framework behavior, Python
standard-library behavior, or private implementation details with no observable
contract.

## Test shape

Use Arrange–Act–Assert with visual separation:

```python
def test_ingest_when_revision_is_unchanged_returns_noop() -> None:
    repository = FakeConversationRepository(existing_revision="revision-1")
    use_case = IngestConversation(repository=repository)
    snapshot = conversation_snapshot(revision="revision-1")

    result = use_case(snapshot)

    assert result.status == IngestStatus.UNCHANGED
    assert repository.saved_snapshots == []
```

Each test should communicate one behavior. Multiple assertions are appropriate
when they describe one outcome.

Assert public results, state changes, emitted domain events, or errors. Avoid
asserting private methods, incidental call order, or the exact sequence of
internal helper calls.

## Test doubles

Use small, handwritten fakes for application ports when state matters:

```python
class FakeConversationRepository:
    def __init__(self) -> None:
        self.saved_snapshots: list[ConversationSnapshot] = []

    def save(self, snapshot: ConversationSnapshot) -> None:
        self.saved_snapshots.append(snapshot)
```

Fakes must implement the real port and expose only the controls and observations
needed by tests.

Use `unittest.mock` sparingly:

- create mocks with `spec_set` against the port;
- mock only outbound boundaries;
- use a mock when the interaction itself is the behavior;
- do not patch domain objects, application internals, or functions merely to
  make implementation-specific assertions; and
- do not mock a concrete adapter to test another concrete adapter.

If a test needs many mocks, reconsider the production boundary or classify the
test as integration.

## Fixtures and builders

Keep fixtures local to a test module by default. Move a fixture to
`tests/unit/conftest.py` only when it is broadly shared and has one clear
purpose.

Do not use autouse fixtures for domain or application state.

Use explicit builders for canonical records with sensible valid defaults:

```python
def conversation_snapshot(
    *,
    conversation_id: str = "conversation-1",
    revision: str = "revision-1",
) -> ConversationSnapshot: ...
```

Override only values relevant to the scenario. Builders must not hide I/O,
randomness, current time, or database setup.

Use realistic but synthetic values. Never copy personal prompts, email
addresses, absolute home paths, or raw local transcripts into unit tests.

## Determinism

Inject nondeterministic capabilities through ports or explicit parameters:

- clock/time;
- ID generation;
- source revision;
- platform;
- home and workspace roots; and
- ordering inputs.

Use fixed UTC datetimes and stable IDs. Never use `sleep`, retry loops,
unseeded randomness, the current machine's home directory, or test-order
dependencies.

Do not use `tmp_path` in unit tests. Pass in-memory records or path strings to
pure functions; filesystem behavior belongs in integration tests.

## Parametrization

Use `pytest.mark.parametrize` for the same behavior across meaningful inputs,
especially:

- exact `SKILL.md` positive cases;
- negative filename, glob, directory, shell, grep, and edit cases;
- supported source buckets;
- readiness states;
- malformed frontmatter; and
- error mappings.

Give complex cases readable IDs. Do not compress unrelated behaviors into one
large parameter matrix.

## Exceptions and diagnostics

Use `pytest.raises` around only the operation expected to fail:

```python
with pytest.raises(InvalidSnapshotError) as raised:
    validate_snapshot(snapshot)

assert raised.value.code == "missing_conversation_id"
```

Prefer stable error types, codes, and structured fields over full-message
equality. Assert message text only when wording is part of the public contract.

For operations that return diagnostics instead of raising, assert the stable
diagnostic code and relevant safe fields.

## Boundaries specific to Skillscope

- Test application use cases against harness and repository ports, not Cursor
  or SQLite implementations.
- Test Cursor normalization from in-memory native dictionaries. Reading JSONL
  fixtures from disk is an integration test.
- Test repository decisions as pure policies when possible; test actual SQL in
  the integration suite.
- Test REST mapping as pure functions only. Route registration, validation,
  middleware, OpenAPI, and status codes belong in integration tests.
- Confirm unknown or failed read evidence never becomes `skill.activated`.
- Confirm repeated activations retain distinct stable identities.
- Confirm missing payloads preserve the path and mark the snapshot unavailable.

## Quality requirements

Every test must be:

- behavior-focused;
- deterministic;
- isolated;
- readable without opening the implementation;
- free of production secrets and machine-specific state; and
- fast enough to run continuously during development.

Do not pursue a coverage percentage by testing incidental lines. New or changed
domain and application branches require meaningful unit coverage, including
negative and error paths.

## Running the suite

The canonical command is:

```bash
pytest tests/unit
```

Unit tests must not require network access, external services, an existing
Skillscope database, Cursor installation, user hooks, or files outside the
repository.

## Review checklist

- The test belongs at the unit layer.
- It mirrors the production module under `tests/unit`.
- Its name states behavior, condition, and outcome.
- It has no I/O or framework startup.
- It tests public behavior rather than implementation details.
- Ports use small fakes or narrowly specified mocks.
- Time, IDs, paths, and revisions are deterministic.
- Fixtures are explicit and synthetic.
- Parameterization improves clarity rather than hiding behavior.
- Error and negative paths are covered.
- The test passes alone and in any suite order.
