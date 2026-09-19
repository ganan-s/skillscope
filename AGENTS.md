# Skillscope agent guidance

## Backend architecture

The Python backend uses hexagonal architecture. Follow the project skills:

- `backend-hexagonal-architecture`
- `backend-unit-testing`
- `backend-integration-testing`
- `backend-e2e-testing`

Keep domain and application code independent of FastAPI, SQLite, Cursor-native
formats, the filesystem, and CLI frameworks. Concrete adapters are wired only
from the composition root.

## Python tooling

Use uv for Python environments, dependencies, and commands. Do not use
standalone `pip` or manually managed virtual environments.

After changing Python code, always run:

```bash
uv run ruff check .
uv run ruff format --check .
```

If formatting is required, run `uv run ruff format .`, then rerun both checks.
Do not report Python work complete while either check fails.

Run tests proportional to the change:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e
```

Run the full suite with `uv run pytest` before handing off broad backend
changes. E2E tests require a Docker-compatible runtime.
