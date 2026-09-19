---
name: backend-e2e-testing
description: Enforces Skillscope's end-to-end testing conventions for installed wheels, subprocesses, Testcontainers, Docker-compatible runtimes, live HTTP requests, and Playwright. Use when creating or reviewing tests under tests/e2e or testing packaged service and dashboard workflows.
---

# Backend end-to-end testing

Apply these conventions to Skillscope E2E work. Also apply
`backend-integration-testing` when deciding whether a test needs a real process
boundary.

Read `docs/06-e2e-test-framework.md` before changing the E2E harness or suite.

## Boundary

An E2E test must require at least one of:

- an installed wheel or console entry point;
- a separately running Skillscope process;
- a real HTTP socket; or
- a browser.

In-process CLI, FastAPI TestClient, real SQLite, and filesystem fixtures alone
are integration tests. Do not move broad integration coverage into E2E.

## Locations

Use:

```text
tests/e2e/
  service/
  api/
```

Use the frontend toolchain's Playwright directory for UI tests. Mark Python E2E
tests with both `e2e` and `docker` when they require Testcontainers.

## Installed artifact

- Build the wheel with `uv`.
- Install the wheel in the test environment; never use an editable install.
- Do not import Skillscope from the source checkout to exercise product
  behavior.
- Share one built wheel per pytest session.
- Assert public process output, exit status, files, HTTP responses, or browser
  behavior.

## Testcontainers

- Use Python Testcontainers to own container start, stop, networking, port
  mapping, logs, and cleanup.
- Use a test-only container image. Docker support does not imply a production
  container deployment.
- Mount only the built wheel, synthetic fixtures, and temporary test state.
- Never mount the real home directory, Cursor data, Skillscope database, or
  Docker socket.
- Use random mapped host ports.
- Use bounded process or HTTP readiness checks; never use arbitrary sleeps.
- Treat missing Docker as a clear failure when the E2E suite is selected.
- Include sanitized container logs in assertion failures.

## Data setup

- Use synthetic fixtures with fixed ids and UTC timestamps.
- Invoke the installed `skillscope ingest` for true E2E store setup.
- Do not seed the E2E database with ad hoc SQL.
- Give each test isolated writable state.
- Remove native source fixtures before snapshot-independence assertions.
- Never read the user's actual home, harness data, or database.

## Assertion ownership

### Service

Test installation, console entry points, process lifecycle, package resources,
and ingest-to-store behavior.

### Live API

Test a narrow core flow through real HTTP. Keep exhaustive route validation,
serialization, and error matrices in `tests/integration/api`.

### Playwright

Test user-visible dashboard journeys with accessible selectors or stable test
ids. Do not re-test parser rules, SQL details, or every API field.

## Commands

Run:

```bash
uv run pytest tests/e2e
```

After changing Python:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Review checklist

- The behavior requires a packaged artifact, process, socket, or browser.
- The test uses production composition and installed artifacts.
- Testcontainers owns container lifecycle.
- Fixtures and writable state are isolated and synthetic.
- Readiness is bounded and has no arbitrary sleep.
- Assertions stay at the public boundary.
- Failures include useful, sanitized diagnostics.
- The test does not duplicate broad integration coverage.
