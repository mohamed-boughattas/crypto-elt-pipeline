PROJECT_ROOT := env("PWD")
export DAGSTER_HOME := PROJECT_ROOT + "/.dagster_home"
DB_PATH := "data/crypto.duckdb"

# Dynamically read enabled coins from config/coins.yaml
COINS := `uv run python -c "import yaml; print(' '.join([c['id'] for c in yaml.safe_load(open('config/coins.yaml'))['coins'] if c.get('enabled', True)]))"`

# Default recipe - list all available recipes
default:
    just --list

# =============================================================================
# Setup
# =============================================================================

# Setup environment (uv sync + create dirs)
setup:
    uv sync
    mkdir -p data {{DAGSTER_HOME}}
    touch {{DAGSTER_HOME}}/dagster.yaml

# Generate dbt seed from coins.yaml
generate-seed:
    uv run python dbt_project/scripts/generate_seed.py

# Validate coins against config before pipeline execution
validate-coins:
    @echo "🔍 Validating coin list against config/coins.yaml..."
    @uv run python -c "import yaml; coins=[c['id'] for c in yaml.safe_load(open('config/coins.yaml'))['coins'] if c.get('enabled', True)]; print(f'Found {len(coins)} enabled coins: {\" \".join(coins)}')"
    @echo "✅ All coins validated successfully!"

# Preview pipeline execution without running
dry-run:
    @echo "🔍 Pipeline Dry-Run Preview"
    @echo ""
    @echo "📦 Coins to process: {{COINS}}"
    @echo ""
    @echo "🔄 Bronze Layer Assets:"
    @echo "   - raw/crypto_prices (partitioned by coin)"
    @echo ""
    @echo "🥈 Silver Layer Assets:"
    @echo "   - staging/stg_crypto_prices"
    @echo ""
    @echo "🥇 Gold Layer Assets:"
    @echo "   - mart/fct_crypto_candlesticks"
    @echo ""
    @docker info >/dev/null 2>&1 && echo "✅ Docker is running" || echo "❌ Docker is not running"

# List all enabled coins from config
list-coins:
    @echo "Available coins (from config/coins.yaml):"
    @uv run python -c "import yaml; [print(f'  - {c[\"id\"]} ({c[\"name\"]})') for c in yaml.safe_load(open('config/coins.yaml'))['coins'] if c.get('enabled', True)]"

# =============================================================================
# Pipeline
# =============================================================================

# Full pipeline: Bronze → Silver → Gold (all enabled coins)
pipeline: setup validate-coins
    @docker info >/dev/null 2>&1 || { echo "❌ Docker is not running!"; exit 1; }
    @echo "⚡ Running pipeline..."
    @echo ""
    @echo "📦 Bronze Layer: Ingesting raw data..."
    @for coin in {{COINS}}; do uv run dg launch --assets 'raw/crypto_prices' --partition $$coin || exit 1; done
    @echo ""
    @echo "🔄 Silver & Gold Layers: Running dbt transformations..."
    @uv run dg launch --assets 'staging/stg_crypto_prices,mart/fct_crypto_candlesticks' || exit 1
    @echo ""
    @echo "✅ Pipeline complete!"

# Single coin pipeline: just pipeline-coin bitcoin
pipeline-coin coin:
    @docker info >/dev/null 2>&1 || { echo "❌ Docker is not running!"; exit 1; }
    @echo "⚡ Running pipeline for {{coin}}..."
    @echo ""
    @echo "📦 Bronze Layer: Ingesting raw data..."
    @uv run dg launch --assets 'raw/crypto_prices' --partition {{coin}}
    @echo ""
    @echo "✅ Pipeline complete for {{coin}}!"
    @echo ""
    @echo "💡 Note: dbt transformations run on full dataset. Run 'just pipeline' to process all coins."

# One command to run everything
start: pipeline dashboard

# =============================================================================
# Development
# =============================================================================

# Launch Dagster development server
dev: setup
    uv run dg dev

# Launch Streamlit dashboard
dashboard:
    @test -f {{DB_PATH}} || just pipeline
    PYTHONPATH=. uv run streamlit run streamlit_dashboard/dashboard.py

# Launch FastAPI server
api:
    @test -f {{DB_PATH}} || just pipeline
    PYTHONPATH=. uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# =============================================================================
# Testing & Quality
# =============================================================================

# Run tests
test: setup
    uv run pytest tests/ -v

# Run tests with coverage
test-cov: setup
    uv run pytest tests/ -v \
        --cov=src/crypto_elt_pipeline \
        --cov=streamlit_dashboard/indicators \
        --cov=api \
        --cov-report=term-missing

# Run type checking
typecheck: setup
    uv run pyright src/crypto_elt_pipeline/

# Run linting and format checks
lint: setup
    uv run ruff check src/ tests/ api/ streamlit_dashboard/
    uv run ruff format --check src/ tests/ api/ streamlit_dashboard/

# Find dead code with vulture
dead-code:
    uv run vulture src/ api/ streamlit_dashboard/ tests/ vulture_whitelist.py --min-confidence 80

# Lint dbt models with SQLFluff
lint-dbt: setup
    cd dbt_project && uv run sqlfluff lint models/

# Fix dbt linting issues with SQLFluff
lint-dbt-fix: setup
    cd dbt_project && uv run sqlfluff fix models/

# Run dbt tests
test-dbt: setup
    cd dbt_project && uv run dbt test

# Install dbt packages (run after editing packages.yml)
dbt-deps: setup
    cd dbt_project && uv run dbt deps

# Run only elementary-tagged data observability tests
test-elementary: setup
    cd dbt_project && uv run dbt test --select tag:elementary

# Generate elementary observability HTML report (requires populated DB)
# Uses uvx because elementary-data conflicts with airbyte's pytz pin
observability: dbt-deps
    cd dbt_project && uvx --with 'elementary-data[duckdb]' edr report

# =============================================================================
# Maintenance
# =============================================================================

# Clean generated files (preserves .dagster_home for run history)
clean:
    @echo "🧹 Cleaning generated files..."
    @rm -rf data/*.duckdb data/*.duckdb.wal dbt_project/target
    @echo "✅ Clean complete!"
    @rm -rf source-* /tmp/airbyte
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Deep clean (including .dagster_home and .venv)
deep-clean:
    @echo "💣 Deep cleaning all generated files..."
    @rm -rf data/*.duckdb data/*.duckdb.wal .dagster_home dbt_project/target .venv
    @echo "✅ Deep clean complete!"
    @rm -rf source-* /tmp/airbyte
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Status
# =============================================================================

# Pipeline status - quick health check without opening Dagster UI
status:
    @test -f {{DB_PATH}} && echo "✅ Database exists: {{DB_PATH}}" || echo "❌ Database not found: {{DB_PATH}}"
    @uv run python -c "import os, sys; sys.path.insert(0, '.'); from crypto_elt_pipeline.utils.crypto_db import get_latest_timestamp; import pendulum; conn = __import__('duckdb').connect('{{DB_PATH}}', read_only=True); coins = conn.execute('SELECT DISTINCT coin FROM raw.crypto_prices ORDER BY coin').fetchall(); [print('  - {}: {:,} records'.format(c[0], conn.execute('SELECT COUNT(*) FROM raw.crypto_prices WHERE coin = \\'' + c[0] + '\\'').fetchone()[0])) for c in coins]"

# =============================================================================
# Security
# =============================================================================

# Scan Python dependencies for vulnerabilities
pip-audit:
    @echo "🔒 Running pip-audit (Python dependency scanner)..."
    @uv run pip-audit --skip-editable || true

# Scan code for security issues
bandit:
    @echo "🔍 Running bandit (Code-level security scanner)..."
    @uv run bandit -r . -ll -c .bandit || true

# Run all security scans
security: pip-audit bandit
