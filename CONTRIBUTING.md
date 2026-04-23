# Developer Guide

This is a personal portfolio project. This guide covers how to work on the codebase.

## Setup

```bash
# Install dependencies and create required directories
just setup

# Install pre-commit hooks
uv run pre-commit install
```

Docker must be running before executing pipeline commands (`just pipeline`, `just start`).

## Development Commands

```bash
just lint           # Lint and format checks (ruff + ruff format + sqlfluff)
just typecheck      # Type checking with pyright
just test           # Run all tests (119 tests)

just pipeline       # Run full pipeline (Bronze → Silver → Gold)
just status         # Check pipeline health and data freshness

just dev            # Launch Dagster UI (localhost:3000)
just dashboard      # Launch Streamlit dashboard (localhost:8501)
just api            # Launch FastAPI server (localhost:8000)
```

## Verification Order

Before pushing changes, run in order:

```bash
just lint
just typecheck
just test
```

## Code Style

**Python**: Ruff (auto-fixed via pre-commit or `just lint`)
**SQL (dbt)**: SQLFluff with DuckDB dialect (`just lint` or `cd dbt_project && uv run sqlfluff lint models/`)
**Commits**: Conventional format (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)

## Writing Tests

- Tests live in `tests/`
- Naming: `test_*.py`, classes `Test*`, functions `test_*()`
- Shared fixtures in `conftest.py`
- Mock `airbyte_source` fixture prevents hitting real CoinGecko API

## Making Changes

1. Edit code
2. Run `just lint` — fix any issues
3. Run `just typecheck` — fix type errors
4. Run `just test` — all 119 tests must pass
5. Push

## Cleanup

```bash
just clean       # Remove generated files (preserves database and run history)
just deep-clean  # Full reset including database and .dagster_home
```
