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
