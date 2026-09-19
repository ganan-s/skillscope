# Skillscope

Skillscope is a local dashboard for reviewing which `SKILL.md` files were
loaded in closed agent conversations.

The project is under active development. See:

- [`docs/01-vision.md`](docs/01-vision.md)
- [`docs/02-backend-architecture.md`](docs/02-backend-architecture.md)
- [`docs/03-ingestion-contract.md`](docs/03-ingestion-contract.md)
- [`docs/05-api-resource-design.md`](docs/05-api-resource-design.md)
- [`docs/06-e2e-test-framework.md`](docs/06-e2e-test-framework.md)
- [`docs/openapi/v1.yaml`](docs/openapi/v1.yaml)

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

The E2E suite requires a Docker-compatible runtime:

```bash
uv run pytest tests/e2e
```

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
