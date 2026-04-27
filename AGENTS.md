# AGENTS.md — Crypto ELT Pipeline

## Stack

- **Package manager**: `uv` (not pip). All commands use `uv run`.
- **Python**: 3.12 pinned in `.python-version`.
- **Orchestration**: Dagster — code location: `src/crypto_elt_pipeline/definitions.py`.
- **CLI**: Use `dg` (Dagster's CLI), not `dagster` or `dagit`. `dg dev`, `dg launch`.
- **Dagster**: `dagster==1.12.14` (hard-pinned). `dagster-dbt>=0.28.14`, `dagster-duckdb-polars>=0.28.14` (lower bounds only).
- **Database**: DuckDB at `data/crypto.duckdb` (gitignored).
- **Data observability**: elementary — dbt-native anomaly detection (volume, freshness, column stats, schema changes). CLI: `edr`. Tests tagged `tag:elementary`.

## Architecture

- **Medallion layers**: `raw` (Bronze) → `staging` (Silver, incremental dbt) → `mart` (Gold, table).
- **Single source of truth**: `config/coins.yaml` defines all 10 coins. Run `just generate-seed` to regenerate `dbt_project/seeds/coins_config.csv` from it.
- **Ownership**: Dagster owns Bronze (PyAirbyte → Polars). dbt owns Silver and Gold via `DbtCliResource`.
- **Gold model**: `fct_crypto_candlesticks` with OHLC + SMA + Bollinger Bands + RSI + MACD (RSI/MACD are dbt macros, not Python).
- **Sensors**: All in `defs/schedules.py`. No separate `sensors.py`.
- **Dagster definitions**: `definitions.py` uses `@definitions` decorator + `load_from_defs_folder` (component-based pattern), not the traditional `Definitions()` constructor.

## Commands

```bash
# Verification (run in this order)
just lint          # ruff check + ruff format --check on src/ and tests/ only — does NOT cover api/ or streamlit_dashboard/
just lint-dbt      # SQLFluff on dbt models
just typecheck
just test

# Coverage
just test-cov      # pytest with coverage: src/crypto_elt_pipeline, streamlit_dashboard/indicators, api

# Setup
just setup          # uv sync + create .dagster_home + dagster.yaml
just generate-seed  # Regenerate seeds/coins_config.csv from config/coins.yaml

# Pipeline
just pipeline       # Full pipeline: Bronze (per coin) → Silver → Gold
just pipeline-coin bitcoin  # Single coin (Bronze ONLY — does NOT run Silver/Gold dbt transforms)
just start          # pipeline + dashboard in one command
just status         # Database health check (requires populated DB)

# dbt
just dbt-deps         # Install dbt packages (run after editing packages.yml)
just lint-dbt         # SQLFluff lint on dbt models
just lint-dbt-fix     # SQLFluff auto-fix
just test-dbt         # dbt test (requires dbt deps AND populated DB — run just pipeline first locally)
just test-elementary  # Run only anomaly/schema tests
just observability    # Generate elementary HTML report (requires populated DB; implicitly runs dbt-deps)

# Dev servers
just dev           # Dagster UI (localhost:3000)
just dashboard      # Streamlit (localhost:8501)
just api            # FastAPI (localhost:8000)

# Cleanup
just clean         # Removes generated files, preserves database and .dagster_home
just deep-clean    # Removes everything including database and .dagster_home
```

**Single test**: `uv run pytest tests/test_config.py::TestConfig::test_name -v`

## dbt Quirks

- **profiles.yml** is committed at `dbt_project/profiles.yml` (points to `../data/crypto.duckdb`).
- `stg_crypto_prices` is `incremental` materialization; `fct_crypto_candlesticks` is `table`.
- `dbt_packages/` is gitignored — run `cd dbt_project && uv run dbt deps` before local dbt work.
- **SQLFluff** uses `templater = jinja` and skips templating/parsing rules because custom macros (`get_coin_list`, `calculate_volatility`, `calculate_rsi`, `calculate_macd`) can't be resolved.

## Testing

- `tests/conftest.py` has `mock_airbyte_source` (autouse) — tests never hit the real CoinGecko API.
- `pyproject.toml` suppresses Experimental, Deprecation, and pandera validator warnings.
- Pre-commit hooks: install with `uv run pre-commit install`. Includes ruff, pyright, sqlfluff, and conventional commit validation.

## Environment & Paths

- `DAGSTER_HOME=.dagster_home` — required for Dagster to find `dagster.yaml`.
- `PYTHONPATH=.` — required for Streamlit and FastAPI.
- `.env` is gitignored — use `.env.example`.

## Gotchas

- **Docker required**: PyAirbyte needs Docker running. `just pipeline` checks `docker info` and fails if not running.
- **chardet pin**: Pinned `<6.0.0` in `pyproject.toml` because sqlfluff pulls chardet 6.x which conflicts with requests.
- **CI lint scope is broader**: CI runs `ruff check .` and `ruff format --check .` on the whole repo, but `just lint` only covers `src/ tests/`. After editing `api/` or `streamlit_dashboard/`, also run `ruff check api/ streamlit_dashboard/`.
- **DO NOT** run `uv run dagster` or `uv run dagit` — use `dg` only.
- **Conventional commits enforced**: pre-commit rejects non-conventional messages. Use `feat:`, `fix:`, `chore:`, etc.
- **pip-audit/bandit**: Configured `continue-on-error: true` in CI. They report unfixable transitive vulnerabilities from airbyte's deps — documented in `.pip-audit.toml`.
- **elementary-data vs airbyte**: `edr` CLI uses `uvx` (isolated env) because `airbyte-cdk` pins `pytz==2024.2` while `elementary-data` needs `pytz>=2025.1`. The dbt package itself is SQL-only and has no Python dependency.
- **Coin IDs are NOT ticker symbols**: Use `ripple` (not `xrp`), `avalanche-2` (not `avalanche`), `binancecoin` (not `bnb`). Check `config/coins.yaml` for the correct `id` field.
- **CI job chain**: `lint` and `test` run in parallel → `dbt` job runs after both pass (runs `dbt docs generate` + `edr report`). `security` job runs independently (bandit + Trivy, both `continue-on-error`).
