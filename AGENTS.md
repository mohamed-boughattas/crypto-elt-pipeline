# AGENTS.md — Crypto ELT Pipeline

## Stack

- **Package manager**: `uv` (not pip). All commands use `uv run`.
- **Python**: 3.12 pinned in `.python-version`.
- **Orchestration**: Dagster — code location: `src/crypto_elt_pipeline/definitions.py`.
- **CLI**: Use `dg` (Dagster's CLI), not `dagster` or `dagit`. `dg dev`, `dg launch`.
- **Dagster**: `dagster==1.12.14` (hard-pinned). `dagster-dbt>=0.28.14`, `dagster-duckdb-polars>=0.28.14` (lower bounds only).
- **Database**: DuckDB at `data/crypto.duckdb` (gitignored).
- **Data observability**: elementary — dbt-native anomaly detection. CLI: `edr`. Tests tagged `tag:elementary`.

## Architecture

- **Medallion layers**: `raw` (Bronze) → `staging` (Silver, incremental dbt) → `mart` (Gold, table).
- **Single source of truth**: `config/coins.yaml` defines all 10 coins. Run `just generate-seed` to regenerate `dbt_project/seeds/coins_config.csv` from it.
- **Ownership**: Dagster owns Bronze (PyAirbyte → Polars). dbt owns Silver and Gold via `DbtCliResource`.
- **Gold model**: `fct_crypto_candlesticks` with OHLC + SMA + Bollinger Bands + RSI + MACD (RSI/MACD are dbt macros, not Python).
- **Sensors**: All in `defs/schedules.py`. No separate `sensors.py`.
- **Dagster definitions**: `definitions.py` uses `@definitions` decorator + `load_from_defs_folder` (component-based pattern).
- **API**: `api/` has two routers — `health` (`/health`, `/`) and `market` (`/api/v1/coins`, `/api/v1/candlesticks/{coin}`, `/api/v1/latest`). `get_db_connection` lives in `api.db` (context manager, read-only DuckDB). Routers import it from there.

## Commands

```bash
# Setup (run first before dg dev or dg launch)
just setup          # uv sync + create .dagster_home/dagster.yaml (required for Dagster)
just generate-seed  # Regenerate seeds/coins_config.csv from config/coins.yaml

# Pipeline
just pipeline       # Full pipeline: Bronze (per coin) → Silver → Gold
just pipeline-coin bitcoin  # Single coin (Bronze ONLY — dbt Silver/Gold NOT run)
just validate-coins  # Validate config/coins.yaml without running pipeline
just list-coins     # List all enabled coins from config
just dry-run        # Preview pipeline assets without executing
just start          # pipeline + dashboard combined
just status         # Database health check (requires populated DB)

# dbt
just dbt-deps         # Install dbt packages (run after editing packages.yml)
just lint-dbt         # SQLFluff lint on dbt models
just lint-dbt-fix     # SQLFluff auto-fix
just test-dbt         # Run dbt tests (requires populated DB)
just test-elementary  # Run elementary-tagged tests only
just observability    # Generate elementary HTML report (requires populated DB)

# Verification
just lint          # ruff check + format on src/, tests/, api/, streamlit_dashboard/
just lint-dbt      # SQLFluff on dbt models
just typecheck     # pyright type checking (src/ only)
just test          # pytest
just dead-code     # vulture dead code detection (uses vulture_whitelist.py)
just test-cov      # pytest with coverage

# Dev servers
just dev            # Dagster UI (localhost:3000)
just dashboard      # Streamlit (localhost:8501)
just api            # FastAPI (localhost:8000)

# Security
just pip-audit      # Dependency vulnerability scan
just security       # pip-audit + bandit combined

# Maintenance
just clean          # Remove generated files, preserve .dagster_home
just deep-clean      # Remove everything including .dagster_home and .venv
```

**Single test**: `uv run pytest tests/test_config.py::TestConfig::test_name -v`

## Environment & Paths

- `DAGSTER_HOME=.dagster_home` — required for Dagster to find `dagster.yaml`.
- `PYTHONPATH=.` — required for Streamlit and FastAPI.
- `.env` is gitignored — use `.env.example`. Only variable: `COINGECKO_API_KEY` (optional, for premium CoinGecko access).

## Testing

- `tests/conftest.py` has `mock_airbyte_source` (autouse) — tests never hit the real CoinGecko API.
- `pyproject.toml` suppresses Experimental, Deprecation, and pandera validator warnings.
- Pre-commit pyright runs on `src/crypto_elt_pipeline/` only — `api/` and `streamlit_dashboard/` are excluded by `.pre-commit-config.yaml`.
- Install pre-commit: `uv run pre-commit install`.
- **Patch targets**: When mocking `from X import Y` (e.g. `from crypto_elt_pipeline.constants import DUCKDB_PATH`), patch at the **usage site** (`api.routers.health.DUCKDB_PATH`), not the definition site (`crypto_elt_pipeline.constants.DUCKDB_PATH`). The `health` and `market` routers each import `get_db_connection` from `api.db` — patch it where it's used (`api.routers.health.get_db_connection`), not where it's defined (`api.db.get_db_connection`). Wrong patch targets pass locally (real database exists) but fail in CI (no database).

## dbt Quirks

- **profiles.yml** is committed at `dbt_project/profiles.yml` (points to `../data/crypto.duckdb`).
- `stg_crypto_prices` is `incremental`; `fct_crypto_candlesticks` is `table`.
- `dbt_packages/` is gitignored — run `just dbt-deps` before local dbt work.
- **SQLFluff** uses `templater = jinja` and skips templating/parsing rules because custom macros (`get_coin_list`, `calculate_volatility`, `calculate_rsi`, `calculate_macd`) can't be resolved.

## Gotchas

- **Docker required**: PyAirbyte needs Docker running. `just pipeline` fails if Docker is not running.
- **chardet pin**: Pinned `<6.0.0` in `pyproject.toml` because sqlfluff pulls chardet 6.x which conflicts with requests.
- **DO NOT** run `uv run dagster` or `uv run dagit` — use `dg` only.
- **Conventional commits enforced**: pre-commit rejects non-conventional messages. Use `feat:`, `fix:`, `chore:`, etc.
- **Security in CI**: CI runs **bandit + Trivy** (not pip-audit). `pip-audit` is local-only via `just pip-audit` / `just security`. Bandit uses `continue-on-error: true` in CI; Trivy runs with `--exit-code 0` and uploads SARIF to GitHub Security. Known unfixable transitive vulnerabilities from airbyte's deps are documented in `.pip-audit.toml`.
- **elementary-data vs airbyte**: `edr` CLI uses `uvx` (isolated env) because `airbyte-cdk` pins `pytz==2024.2` while `elementary-data` needs `pytz>=2025.1`. The dbt package itself has no Python dependency.
- **Coin IDs are NOT ticker symbols**: Use `ripple` (not `xrp`), `avalanche-2` (not `avalanche`), `binancecoin` (not `bnb`). Check `config/coins.yaml` for the correct `id` field.
- **CI job chain**: `lint` and `test` run in parallel → `dbt` job runs after both pass. `security` job runs independently. CI also uploads coverage/test results to Codecov and generates dbt docs as artifacts.
