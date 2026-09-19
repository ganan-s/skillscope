# Skillscope

Skillscope is a local dashboard for reviewing which `SKILL.md` files were
loaded in closed agent conversations.

The project is under active development. See:

- [`docs/01-vision.md`](docs/01-vision.md)
- [`docs/02-backend-architecture.md`](docs/02-backend-architecture.md)
- [`docs/03-ingestion-contract.md`](docs/03-ingestion-contract.md)

## Development

Skillscope requires Python 3.12 or newer and uses
[uv](https://docs.astral.sh/uv/) for project and dependency management.

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Apply formatting with:

```bash
uv run ruff format .
```
