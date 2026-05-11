# AGENTS.md — Crypto ELT Pipeline

## Stack

- **Package manager**: `uv` (not pip). All commands use `uv run`.
- **Python**: `>=3.12,<3.15` (pinned in `.python-version`).
- **Orchestration**: Dagster `1.12.14` (hard-pinned). `dagster-dbt>=0.28.14`, `dagster-duckdb-polars>=0.28.14`.
- **CLI**: Use `dg` (Dagster CLI), not `dagster`/`dagit`. `dg dev`, `dg launch`.
- **dbt**: Core `1.11.x` via `dbt-duckdb>=1.10.0`. dbt packages in `dbt_packages/` (gitignored) — run `just dbt-deps` first.
- **Database**: DuckDB at `data/crypto.duckdb` (gitignored).
- **Data observability**: elementary — `edr` CLI via `uvx --from elementary-data[duckdb] --python 3.12`. Tests tagged `tag:elementary`.

## Architecture

- **Medallion layers**: `raw` (Bronze) → `staging` (Silver, incremental dbt) → `mart` (Gold, table).
- **Single source of truth**: `config/coins.yaml` defines all 10 coins. Run `just generate-seed` to regenerate `dbt_project/seeds/coins_config.csv` from it.
- **Ownership**: Dagster owns Bronze (PyAirbyte → Polars). dbt owns Silver and Gold via `DbtCliResource`.
- **Dagster definitions**: `definitions.py` uses `@definitions` decorator + `load_from_defs_folder` (component-based pattern).
- **Sensors**: All in `defs/schedules.py`. No separate `sensors.py`.
- **API**: `api/` has two routers — `health` (`/health`, `/`) and `market` (`/api/v1/coins`, `/api/v1/candlesticks/{coin}`, `/api/v1/latest`). `get_db_connection` lives in `api.db` (context manager, read-only DuckDB).

## Commands

```bash
# Setup (run first before dg dev or dg launch)
just setup          # uv sync + create .dagster_home/dagster.yaml (telemetry opt-out)
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
just test-dbt         # Run dbt tests — excludes elementary_all_columns_anomalies (see test-elementary)
just test-elementary  # Run elementary-tagged tests only
just observability    # Generate elementary HTML report: runs elementary models + tests + edr report

# Verification
just lint          # ruff check + format on src/, tests/, api/, streamlit_dashboard/
just lint-dbt      # SQLFluff on dbt models
just typecheck     # pyright type checking (src/ only)
just test          # pytest
just test-smoke    # Bash smoke test for all just recipes (scripts/smoke_test.sh)
just dead-code     # vulture dead code detection (uses vulture_whitelist.py)
just test-cov      # pytest with coverage

# Dev servers
just dev            # Dagster UI (localhost:3000)
just dashboard      # Streamlit (localhost:8501)
just api            # FastAPI (localhost:8000)

# Security
just pip-audit      # Dependency vulnerability scan (local only)
just bandit         # Code-level security scanner
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
- **Patch targets**: When mocking `from X import Y` (e.g. `from crypto_elt_pipeline.constants import DUCKDB_PATH`), patch at the **usage site** (`api.routers.health.DUCKDB_PATH`), not the definition site. The `health` and `market` routers each import `get_db_connection` from `api.db` — patch it where it's used, not where it's defined. Wrong patch targets pass locally (real database exists) but fail in CI.

## dbt Quirks

- **profiles.yml** is committed at `dbt_project/profiles.yml` (points to `../data/crypto.duckdb`).
- `stg_crypto_prices` is `incremental`; `fct_crypto_candlesticks` is `table`.
- `dbt_packages/` is gitignored — run `just dbt-deps` before local dbt work.
- **SQLFluff** uses `templater = jinja` and skips templating/parsing rules because custom macros (`get_coin_list`, `calculate_volatility`, `calculate_rsi`, `calculate_macd`) can't be resolved.
- **DuckDB window function nesting**: DuckDB cannot nest window functions (`avg(...) over (...)` inside `avg(...) over (...)`). The `fct_crypto_candlesticks` gold model uses 7 CTEs to avoid this: MACD signal and histogram are computed in a downstream `with_macd_signal` CTE that consumes a materialized `macd` column from `indicators_base`, not inline window expressions.
- **Dagster `--exclude` lost on subsetted execution**: The `@dbt_assets` decorator's `exclude="tag:elementary"` is overridden by Dagster during subsetted execution. Must pass `--exclude tag:elementary` explicitly in `dbt.cli(["build", "--exclude", "tag:elementary"])`.

## Gotchas

- **Docker required**: PyAirbyte needs Docker running. `just pipeline` fails if Docker is not running.
- **chardet pin**: Pinned `<6.0.0` in `pyproject.toml` because sqlfluff pulls chardet 6.x which conflicts with requests.
- **DO NOT** run `uv run dagster` or `uv run dagit` — use `dg` only.
- **Conventional commits enforced**: pre-commit rejects non-conventional messages. Use `feat:`, `fix:`, `chore:`, etc.
- **Security in CI**: CI runs **bandit + Trivy** (not pip-audit). `pip-audit` is local-only via `just pip-audit` / `just security`. Bandit uses `continue-on-error: true`; Trivy runs with `--exit-code 0` and uploads SARIF. Known unfixable transitive vulnerabilities from airbyte's deps documented in `.pip-audit.toml`.
- **elementary-data vs airbyte**: `edr` CLI uses `uvx --from elementary-data[duckdb] --python 3.12` (isolated env) because `airbyte-cdk` pins `pytz==2024.2` while `elementary-data` needs `pytz>=2025.1`. The dbt package itself has no Python dependency.
- **edr absolute path requirement**: `edr` runs its internal dbt from the `uvx` cache directory, where relative paths in `profiles.yml` resolve incorrectly. The `observability` recipe temporarily swaps the relative path to an absolute path before calling `edr`.
- **Coin IDs are NOT ticker symbols**: Use `ripple` (not `xrp`), `avalanche-2` (not `avalanche`), `binancecoin` (not `bnb`). Check `config/coins.yaml` for the correct `id` field.
- **CI job chain**: `lint` and `test` run in parallel → `dbt` job runs after both pass. `security` job runs independently. CI also uploads coverage/test results to Codecov and generates dbt docs as artifacts.
- **elementary all_columns_anomalies overflow**: DuckDB `DECIMAL(28,6)` cannot hold crypto-scale values (e.g., Bitcoin `market_cap` ≈ 2×10^23). These tests are excluded from `test-dbt` via `--exclude elementary_all_columns_anomalies`. The `observability` recipe excludes all columns for `fct_crypto_candlesticks` and `market_cap/price/volume` for `stg_crypto_prices`.
- **unnest_market_data array truncation**: CoinGecko API returns mismatched array lengths for prices/market_caps/volumes (different internal update frequencies). The function truncates to the shortest array and logs a warning instead of raising `ValueError`.
- **just pipeline shebang recipe**: Uses `#!/usr/bin/env bash` shebang instead of `set -euo pipefail` + `$$` escaping because just 1.51.0 `$$` escape does not work as documented inside for-loops.
- **Streamlit + DuckDB `@st.cache_resource`**: `streamlit_dashboard/data.py` caches a single DuckDB connection via `@st.cache_resource`. Never use `with get_connection() as conn:` — the `with` block calls `__exit__` which closes the cached connection permanently. Use `conn = get_connection()` directly (no context manager), same as `get_available_coins` and `get_market_data` already do.

## Key Files

- `justfile`: All `just` recipes
- `scripts/smoke_test.sh`: Bash smoke test for all just recipes
- `src/crypto_elt_pipeline/defs/assets/dbt.py`: `crypto_dbt_assets` — Dagster-dbt integration with `--exclude tag:elementary` in both decorator and `cli()`
- `src/crypto_elt_pipeline/utils/crypto_transform.py`: `unnest_market_data()` — truncates mismatched arrays with warning log
- `dbt_project/models/marts/fct_crypto_candlesticks.sql`: Gold model with 7-CTE structure (avoids DuckDB nested window function error)
- `dbt_project/models/staging/staging.yml`: `elementary.all_columns_anomalies` excludes `market_cap|price|volume`
- `dbt_project/models/marts/marts.yml`: `elementary.all_columns_anomalies` excludes all columns (all overflow DECIMAL(28,6))
- `dbt_project/macros/financial_calculations.sql`: RSI/MACD macros — note `calculate_macd_signal` generates nested window functions when called inline, hence the 7-CTE model structure
