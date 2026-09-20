# Skillscope evaluation: backend-testing-pilot 1.0.0

Created: 2026-09-20T01:45:59.314525+00:00

This is a project-specific evaluation record, not a skill quality score.
Expectation provenance: Proposed evaluation expectations derived from the current Skillscope project instructions, not historical failures or observed agent outcomes. Tasks are authored scenarios. Source references are exact excerpts; a run must preserve the actual instruction versions it evaluates. Required and allowed skills describe task applicability, not permission to read files. Additional reads, including shared AGENTS.md guidance or architecture skills, are not selection failures.

## Preserved context

- Case set SHA-256: `7e7d4df99d4a0cb47fe89a2f030d91f3fa42bda58f9cb6fa38a2de2b4a3eb53a`
- Source manifest SHA-256: `91112522d4c944030ead032005562fc1fc837f9d524eea458609b9afac13809b`
- Project revision: `7edf1a71965d26a58429dfdcf7e92009d06a2400`
- Working-tree status entries: 13 (recorded in JSON; non-source project files are not snapshotted).
- Full input specifications, source contents, evidence and cited artifact contents are preserved in `report.json`.
- No agent execution evidence supplied; behavior remains unverified.

## Static command consistency

- **backend-unit-testing: static_inconsistency** — .cursor/skills/backend-unit-testing/SKILL.md:233 shows `pytest tests/unit` while AGENTS.md requires uv. Propose `uv run pytest tests/unit`; command consistency only, behavior unverified.
  - Evidence `.cursor/skills/backend-unit-testing/SKILL.md`: 'pytest tests/unit'
  - Evidence `AGENTS.md`: 'Use uv for Python environments, dependencies, and commands.'
- **backend-integration-testing: static_inconsistency** — .cursor/skills/backend-integration-testing/SKILL.md:286 shows `pytest tests/integration` while AGENTS.md requires uv. Propose `uv run pytest tests/integration`; command consistency only, behavior unverified.
  - Evidence `.cursor/skills/backend-integration-testing/SKILL.md`: 'pytest tests/integration'
  - Evidence `AGENTS.md`: 'Use uv for Python environments, dependencies, and commands.'
- **backend-e2e-testing: static_check_clear** — No bare pytest invocation in shell fences. This narrow text check does not establish command compliance or general skill quality.

## Per-skill findings

### backend-unit-testing

Version SHA-256: `736e36c3db7e9c83c59bd37b5e8a23964c2c3b38d46a68106751fcae8094f75f`
Required in: unit-native-record-memory, unit-application-port, boundary-jsonl-fixture.
Finding counts (not a score): {'missing_evidence': 15}. Shared-case findings may appear under more than one skill; they do not establish individual causality.

### backend-integration-testing

Version SHA-256: `b375a056b267b0df9b4f4b9bbdc805ff59364789bcd512e93e06392f8790985d`
Required in: boundary-jsonl-fixture, integration-sqlite-rollback, integration-fastapi-client, integration-cli-runner, boundary-testclient-not-e2e.
Finding counts (not a score): {'missing_evidence': 23}. Shared-case findings may appear under more than one skill; they do not establish individual causality.

### backend-e2e-testing

Version SHA-256: `a2ff6225e082165cb59df173b2d56d0a863deb846593f4095cf2b7b2fc4fa8d6`
Required in: e2e-installed-entrypoint, e2e-live-snapshot-api, boundary-testclient-not-e2e.
Finding counts (not a score): {'missing_evidence': 14}. Shared-case findings may appear under more than one skill; they do not establish individual causality.

## Per-case evidence

### unit-native-record-memory: Pure native-record normalization

Add focused regression tests for native read-record normalization from dictionaries already in memory. Cover a successful read of exact SKILL.md, a failed read, and a read with unknown outcome. Do not change discovery or file loading.

Expected applicability: backend-unit-testing.
Selection rationale: Pure adapter normalization is unit work. Native Cursor-shaped input alone does not make a test integration work; the presence of real I/O determines the boundary. Other skill reads are observations rather than failures.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Place regression tests under tests/unit, organized with the pure adapter code they exercise.
- **unit_location: missing_evidence** — Needs artifact/execution review: Place regression tests under tests/unit, organized with the pure adapter code they exercise.
- Check: Pass synthetic native dictionaries directly; do not read a JSONL fixture or use tmp_path, SQLite, HTTP clients, subprocesses, clock, or environment I/O in these tests.
- **in_memory_inputs: missing_evidence** — Needs artifact/execution review: Pass synthetic native dictionaries directly; do not read a JSONL fixture or use tmp_path, SQLite, HTTP clients, subprocesses, clock, or environment I/O in these tests.
- Check: Verify that failed and unknown read outcomes do not produce skill.activated; an exact filename alone is insufficient.
- **failed_unknown_read_negative: missing_evidence** — Needs artifact/execution review: Verify that failed and unknown read outcomes do not produce skill.activated; an exact filename alone is insufficient.
- Check: Invoke Python checks through uv, including uv run pytest tests/unit and the required Ruff checks after Python changes.
- **commands_use_uv: missing_evidence** — Needs artifact/execution review: Invoke Python checks through uv, including uv run pytest tests/unit and the required Ruff checks after Python changes.

### unit-application-port: Application behavior through a fake port

Add a regression test for how IngestConversations handles a snapshot writer returning unchanged. Supply one ready synthetic snapshot through a fake harness port and a fake ConversationSnapshotWriter whose persist method returns unchanged. Verify that the application increments unchanged in both its returned IngestSummary and recorded ingest metadata, with no inserted, updated, or failed count. This tests application handling of a port result; actual replacement and revision idempotency belong to the real writer's integration tests.

Expected applicability: backend-unit-testing.
Selection rationale: The tested behavior is application orchestration through ports: converting the writer's unchanged result into public summary and metadata counts. It does not establish SQLite replacement or idempotency behavior. The architecture skill may legitimately apply alongside the unit-testing skill.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Use small handwritten fakes for the harness, ConversationSnapshotWriter, and IngestMetadataWriter ports. The snapshot writer returns unchanged when the application calls persist; the metadata writer captures the public ingest metadata. Do not construct SQLite or patch application internals.
- **fake_repository_port: missing_evidence** — Needs artifact/execution review: Use small handwritten fakes for the harness, ConversationSnapshotWriter, and IngestMetadataWriter ports. The snapshot writer returns unchanged when the application calls persist; the metadata writer captures the public ingest metadata. Do not construct SQLite or patch application internals.
- Check: Assert unchanged is one and inserted, updated, and failed are zero in the returned IngestSummary and recorded IngestMetadata for the ready snapshot. These assertions verify application handling of the unchanged port result; do not claim they prove absence of database replacement or expect the application to skip persist.
- **public_noop_outcome: missing_evidence** — Needs artifact/execution review: Assert unchanged is one and inserted, updated, and failed are zero in the returned IngestSummary and recorded IngestMetadata for the ready snapshot. These assertions verify application handling of the unchanged port result; do not claim they prove absence of database replacement or expect the application to skip persist.
- Check: Use fixed synthetic revisions, IDs, and times as needed; keep tests under tests/unit and free of real filesystem, database, or environment I/O.
- **deterministic_unit_state: missing_evidence** — Needs artifact/execution review: Use fixed synthetic revisions, IDs, and times as needed; keep tests under tests/unit and free of real filesystem, database, or environment I/O.
- Check: Run the focused unit suite and Python checks through uv.
- **commands_use_uv: missing_evidence** — Needs artifact/execution review: Run the focused unit suite and Python checks through uv.

### boundary-jsonl-fixture: A disk fixture is not a unit input

Review and correct a proposed test under tests/unit that uses tmp_path to write native JSONL, then invokes the real Cursor parser to read that file. Preserve this real file-to-parser boundary and classify the test in the appropriate suite; do not replace it with a mock merely to keep the unit path.

Expected applicability: backend-unit-testing, backend-integration-testing.
Selection rationale: Both skills apply to correcting the boundary: unit conventions identify the misplaced I/O and integration conventions govern the real fixture test. Narrowly selecting only one skill is not the objective.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Place the real file-reading test under tests/integration and explain that preserving filesystem I/O is the reason for its classification.
- **integration_reclassification: missing_evidence** — Needs artifact/execution review: Place the real file-reading test under tests/integration and explain that preserving filesystem I/O is the reason for its classification.
- Check: Exercise the real parser with synthetic native-shaped JSONL rather than pre-normalized DTOs or a mocked parser.
- **real_synthetic_fixture: missing_evidence** — Needs artifact/execution review: Exercise the real parser with synthetic native-shaped JSONL rather than pre-normalized DTOs or a mocked parser.
- Check: Inject temporary transcript and spool paths with controlled platform/clock inputs; do not scan real Cursor data.
- **isolated_paths: missing_evidence** — Needs artifact/execution review: Inject temporary transcript and spool paths with controlled platform/clock inputs; do not scan real Cursor data.
- Check: Invoke the relevant integration tests and Python checks through uv.
- **commands_use_uv: missing_evidence** — Needs artifact/execution review: Invoke the relevant integration tests and Python checks through uv.

### integration-sqlite-rollback: Atomic replacement with real SQLite

Add coverage proving that an interrupted conversation aggregate replacement rolls back without leaving partial child rows. Exercise the real SQLite adapter and production migrations against an isolated temporary database.

Expected applicability: backend-integration-testing.
Selection rationale: Actual transaction atomicity crosses the application/storage boundary. A unit policy test may accompany it, but it cannot substitute for the real SQLite contract.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Use the real connection factory, production migrations, and repository; do not mock SQLite or manufacture a substitute schema.
- **real_sqlite_migrations: missing_evidence** — Needs artifact/execution review: Use the real connection factory, production migrations, and repository; do not mock SQLite or manufacture a substitute schema.
- Check: Keep each test's database and writable state under explicit temporary paths, with no existing Skillscope database dependency.
- **temporary_database: missing_evidence** — Needs artifact/execution review: Keep each test's database and writable state under explicit temporary paths, with no existing Skillscope database dependency.
- Check: Prove rollback leaves the previous complete aggregate and no partial replacement children through public queries or SQL assertions specifically needed to establish atomicity.
- **observable_atomicity: missing_evidence** — Needs artifact/execution review: Prove rollback leaves the previous complete aggregate and no partial replacement children through public queries or SQL assertions specifically needed to establish atomicity.
- Check: Invoke integration tests and Python checks through uv.
- **commands_use_uv: missing_evidence** — Needs artifact/execution review: Invoke integration tests and Python checks through uv.

### integration-fastapi-client: Read-only API through an in-process client

Add a FastAPI contract test for an unknown conversation ID and verify that serving from a temporary snapshot database does not mutate that store. Use an in-process client and the production application factory.

Expected applicability: backend-integration-testing.
Selection rationale: FastAPI route registration and error mapping are integration behavior even though requests and the app run in one process. A live socket is unnecessary for this task.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Build the real FastAPI application with real query services and a temporary snapshot database; use its in-process client without mocked route handlers.
- **real_in_process_api: missing_evidence** — Needs artifact/execution review: Build the real FastAPI application with real query services and a temporary snapshot database; use its in-process client without mocked route handlers.
- Check: Assert the public unknown-ID status and stable error body rather than private handler calls or database row shapes.
- **public_error_contract: missing_evidence** — Needs artifact/execution review: Assert the public unknown-ID status and stable error body rather than private handler calls or database row shapes.
- Check: Seed the fixture through the real write-side repository or public storage-port builder, then verify serving cannot create, migrate, or mutate it.
- **read_only_store: missing_evidence** — Needs artifact/execution review: Seed the fixture through the real write-side repository or public storage-port builder, then verify serving cannot create, migrate, or mutate it.
- Check: Invoke integration tests and Python checks through uv.
- **commands_use_uv: missing_evidence** — Needs artifact/execution review: Invoke integration tests and Python checks through uv.

### integration-cli-runner: CLI option validation without a process boundary

Add a test for invalid CLI options, checking the exit code and user-facing error through the real command registration and an in-process CLI runner. No installed-package or separate-process behavior needs to be demonstrated.

Expected applicability: backend-integration-testing.
Selection rationale: Real CLI parsing and wiring in one process are integration tests. Reading the E2E boundary guidance is legitimate; classifying this test as E2E solely because it tests a CLI is not justified.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Exercise the real command registration/composition via an in-process runner under tests/integration, without replacing option parsing with mocks.
- **real_in_process_cli: missing_evidence** — Needs artifact/execution review: Exercise the real command registration/composition via an in-process runner under tests/integration, without replacing option parsing with mocks.
- Check: Assert the public CLI exit code and user-facing error; do not assert private helper-call order.
- **cli_public_output: missing_evidence** — Needs artifact/execution review: Assert the public CLI exit code and user-facing error; do not assert private helper-call order.
- Check: Provide explicit temporary paths and any configuration the CLI reads; do not rely on the developer's home, database, or shell environment.
- **isolated_cli_configuration: missing_evidence** — Needs artifact/execution review: Provide explicit temporary paths and any configuration the CLI reads; do not rely on the developer's home, database, or shell environment.
- Check: Invoke integration tests and Python checks through uv.
- **commands_use_uv: missing_evidence** — Needs artifact/execution review: Invoke integration tests and Python checks through uv.

### e2e-installed-entrypoint: Installed-wheel console entry point

Add or extend an installed-artifact smoke test that builds the Skillscope wheel and runs the installed skillscope --version entry point in a Testcontainers-managed test environment. Prove the packaged artifact works without importing product behavior from the checkout.

Expected applicability: backend-e2e-testing.
Selection rationale: The installed wheel and real process are required boundaries. Integration skill co-use is explicitly permitted when deciding that boundary.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Build the wheel with uv, install that wheel non-editably in the test environment, and invoke the installed console entry point; share the build per pytest session.
- **installed_artifact: missing_evidence** — Needs artifact/execution review: Build the wheel with uv, install that wheel non-editably in the test environment, and invoke the installed console entry point; share the build per pytest session.
- Check: Use Testcontainers for lifecycle and cleanup with only the wheel, synthetic fixtures, and temporary state mounted; do not mount the source checkout, real home, Cursor data, database, or Docker socket.
- **testcontainers_isolation: missing_evidence** — Needs artifact/execution review: Use Testcontainers for lifecycle and cleanup with only the wheel, synthetic fixtures, and temporary state mounted; do not mount the source checkout, real home, Cursor data, database, or Docker socket.
- Check: Assert public process exit status and version output. Selected E2E runs must report missing Docker as a clear failure rather than claiming a pass or substituting an in-process check.
- **process_evidence: missing_evidence** — Needs artifact/execution review: Assert public process exit status and version output. Selected E2E runs must report missing Docker as a clear failure rather than claiming a pass or substituting an in-process check.
- Check: Read docs/06-e2e-test-framework.md before changing the harness or suite, place the test under tests/e2e, use e2e/docker markers, and run Python commands through uv.
- **e2e_harness_conventions: missing_evidence** — Needs artifact/execution review: Read docs/06-e2e-test-framework.md before changing the harness or suite, place the test under tests/e2e, use e2e/docker markers, and run Python commands through uv.

### e2e-live-snapshot-api: Live service remains independent of source files

Add a narrow packaged-service E2E scenario: ingest synthetic Cursor fixtures through the installed CLI, remove those native source fixtures, start the installed service, and retrieve the saved conversation over a real HTTP socket. Demonstrate that serving depends on the snapshot rather than live native files.

Expected applicability: backend-e2e-testing.
Selection rationale: This scenario needs installed entry points, a separate service process, and a real socket. Architecture and integration guidance may apply to setup and boundary decisions without invalidating E2E selection.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Use fixed synthetic fixtures and the installed skillscope ingest command to create the snapshot; do not seed the E2E database with ad hoc SQL.
- **installed_ingest_setup: missing_evidence** — Needs artifact/execution review: Use fixed synthetic fixtures and the installed skillscope ingest command to create the snapshot; do not seed the E2E database with ad hoc SQL.
- Check: Remove the native fixture source before asserting that the live API still returns the previously ingested snapshot.
- **source_independence: missing_evidence** — Needs artifact/execution review: Remove the native fixture source before asserting that the live API still returns the previously ingested snapshot.
- Check: Use an installed service managed by Testcontainers and a real HTTP request through a random mapped port, with bounded readiness checks instead of arbitrary sleeps.
- **real_socket_readiness: missing_evidence** — Needs artifact/execution review: Use an installed service managed by Testcontainers and a real HTTP request through a random mapped port, with bounded readiness checks instead of arbitrary sleeps.
- Check: Keep writable state isolated, never mount personal data or the Docker socket, and include sanitized container diagnostics when the scenario fails.
- **isolated_e2e_state: missing_evidence** — Needs artifact/execution review: Keep writable state isolated, never mount personal data or the Docker socket, and include sanitized container diagnostics when the scenario fails.
- Check: Read the E2E framework document before changing the suite, use the applicable e2e/docker markers, and invoke tests and Python checks through uv.
- **e2e_harness_conventions: missing_evidence** — Needs artifact/execution review: Read the E2E framework document before changing the suite, use the applicable e2e/docker markers, and invoke tests and Python checks through uv.

### boundary-testclient-not-e2e: Broad in-process coverage remains integration

Review a proposed E2E test that builds FastAPI in process, opens a temporary SQLite database, and sends requests through TestClient. It never installs a wheel, launches a separate process, opens a real socket, or uses a browser. Recommend the correct test layer and explain the boundary; this is a review-only task.

Expected applicability: backend-integration-testing, backend-e2e-testing.
Selection rationale: Both integration and E2E skills are applicable to a classification decision. Loading E2E guidance here is correct even though the proposed test belongs in integration.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Recommend tests/integration for the described TestClient/SQLite scenario and explicitly identify the absence of an installed-artifact, process, socket, or browser requirement.
- **integration_classification: missing_evidence** — Needs artifact/execution review: Recommend tests/integration for the described TestClient/SQLite scenario and explicitly identify the absence of an installed-artifact, process, socket, or browser requirement.
- Check: Keep the real FastAPI and SQLite boundary in the proposed integration test; do not suggest mocking it into a unit test or adding a gratuitous process merely to retain the E2E label.
- **preserve_real_boundary: missing_evidence** — Needs artifact/execution review: Keep the real FastAPI and SQLite boundary in the proposed integration test; do not suggest mocking it into a unit test or adding a gratuitous process merely to retain the E2E label.

### negative-markdown-copy-only: A prose-only typo does not require testing guidance

Correct a spelling typo in a README heading. This task changes prose only, does not request test advice, and does not change any Python, configuration, commands, or test behavior. Explain briefly whether any of the three pilot testing skills is needed for this task.

Expected applicability: none required.
Selection rationale: No pilot testing skill is substantively applicable to this narrow prose task. Forbidden here applies only to a reviewed judgment claiming a testing skill is needed; it never prohibits reads or treats reads caused by shared AGENTS.md instructions as failure. Nonpilot skills remain outside the assessed selection universe.
Supplied read observations: none (not a compliance judgment).

- **selection: missing_evidence** — No reviewed applicability assessment.
- Check: Explain that none of the three testing skills is required for the described prose-only edit. Do not infer a testing applicability failure merely from reading a skill or shared project guidance.
- **scope_explanation: missing_evidence** — Needs artifact/execution review: Explain that none of the three testing skills is required for the described prose-only edit. Do not infer a testing applicability failure merely from reading a skill or shared project guidance.

## Limits and next step

- Expectations are proposed project specifications, not historical failures.
- Reviewed findings are supplied reviewer judgments; identity and runtime authenticity are not independently verified.
- Supplied reads are observations only. Missing or extra reads do not establish missed selection, over-selection, adherence, or effectiveness.
- Illustrations and agent self-reports cannot establish compliance.
- No agent run is launched. Behavioral improvement and causality remain unverified, including when a static inconsistency is removed.

Capture a case in an isolated workspace, preserve the execution log and produced artifacts, and fill `evidence-template.json` with cited reviews. Run `skillscope evaluate` again with `--evidence` and a new output directory. For a proposed revision, generate a new template against the candidate files and repeat the same cases/settings; do not reuse baseline evidence.
