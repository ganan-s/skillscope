# Skillscope

Skillscope is a local dashboard for reviewing which `SKILL.md` files were
loaded in closed agent conversations.

The project is under active development. See:

- [`docs/01-vision.md`](docs/01-vision.md)
- [`docs/02-backend-architecture.md`](docs/02-backend-architecture.md)
- [`docs/03-ingestion-contract.md`](docs/03-ingestion-contract.md)
- [`docs/04-cursor-poc.md`](docs/04-cursor-poc.md)
- [`docs/05-api-resource-design.md`](docs/05-api-resource-design.md)
- [`docs/06-e2e-test-framework.md`](docs/06-e2e-test-framework.md)
- [`docs/07-hooks-and-dev-ingest.md`](docs/07-hooks-and-dev-ingest.md)
- [`docs/openapi/v1.yaml`](docs/openapi/v1.yaml)

## How ingest works

Cursor transcripts do not include tool results, so a successful `SKILL.md` read
and a failed one look the same on disk. Skillscope therefore needs **opt-in
Cursor hooks** to confirm activations. Hooks append to a local spool; they do
not write the database. `skillscope ingest` later pulls that spool plus
transcripts into SQLite. `skillscope serve` is read-only.

Enable production hooks with:

```bash
cp examples/cursor/hooks.json .cursor/hooks.json
```

Then use Cursor normally, ingest, and serve:

```bash
uv run skillscope ingest --harness cursor
uv run skillscope serve
```

Without hooks, ingest can still record conversations and prompts. It will not
emit `skill.activated`. Full operator and dev-loop detail is in
[`docs/07-hooks-and-dev-ingest.md`](docs/07-hooks-and-dev-ingest.md).
## Quick start

```bash
# 1. Ingest closed Cursor conversations
uv run skillscope ingest --harness cursor

# 2. Build the frontend (requires Node.js 18+)
cd web && npm install && npm run build && cd ..

# 3. Start the dashboard
uv run skillscope serve
```

Open <http://127.0.0.1:8000> in your browser.

## Development

Skillscope requires Python 3.12 or newer and uses
[uv](https://docs.astral.sh/uv/) for project and dependency management.

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The default suite uses synthetic fixtures and does not open Cursor. The E2E
suite requires a Docker-compatible runtime:

```bash
uv run pytest tests/e2e
```

To test against a real local Cursor session, or to replay a sanitized golden
capture, follow [hooks and running ingest](docs/07-hooks-and-dev-ingest.md).

Apply formatting with:

```bash
uv run ruff format .
```

### Frontend development

```bash
cd web
npm install
npm run dev        # Vite dev server with API proxy to :8000
npm run build      # Production build to src/skillscope/web/dist/
```

Run `uv run skillscope serve` in another terminal for the API backend.
