.PHONY: help setup start pipeline pipeline-coin dev dashboard api test test-cov typecheck lint lint-dbt lint-dbt-fix clean deep-clean status

# Configuration
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
export DAGSTER_HOME := $(PROJECT_ROOT)/.dagster_home
DB_PATH = data/crypto.duckdb
# COINS dynamically read from config/coins.yaml (enabled coins only)
COINS := $(shell uv run python -c 'import yaml; print(" ".join([c["id"] for c in yaml.safe_load(open("config/coins.yaml"))["coins"] if c.get("enabled", True)]))')

# Default target
help:
	@echo "Crypto Analysis Pipeline"
	@echo ""
	@echo "Quick Start:"
	@echo "  make start     → Setup + Pipeline + Dashboard (one command!)"
	@echo ""
	@echo "Pipeline Operations:"
	@echo "  make pipeline  → Run data pipeline (all enabled coins)"
	@echo "  make coin=bitcoin pipeline-coin → Run pipeline for specific coin"
	@echo "  make status    → Quick health check without opening Dagster UI"
	@echo ""
	@echo "Development:"
	@echo "  make dev       → Launch Dagster development server"
	@echo "  make dashboard → Launch Streamlit Dashboard"
	@echo "  make api       → Launch FastAPI server"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test      → Run tests"
	@echo "  make test-cov  → Run tests with coverage report"
	@echo "  make typecheck → Run type checking with pyright"
	@echo "  make test-dbt  → Run dbt tests"
	@echo "  make lint      → Run linting and format checks"
	@echo "  make lint-dbt  → Lint dbt models with SQLFluff"
	@echo "  make lint-dbt-fix → Fix dbt linting issues"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean     → Clean database and dbt target (preserves history)"
	@echo "  make deep-clean → Full clean including .venv and .dagster_home"
	@echo ""
	@echo "Utilities:"
	@echo "  make list-coins    → Show all enabled coins from config"
	@echo "  make validate-coins → Validate coin list against config"
	@echo "  make dry-run       → Preview pipeline execution"

# Setup environment
setup:
	@uv sync
	@mkdir -p data $(DAGSTER_HOME)
	@touch $(DAGSTER_HOME)/dagster.yaml

# Validate coins against config before pipeline execution
validate-coins:
	@echo "🔍 Validating coin list against config/coins.yaml..."
	@uv run python -c "import yaml; coins=[c['id'] for c in yaml.safe_load(open('config/coins.yaml'))['coins'] if c.get('enabled', True)]; print(f'Found {len(coins)} enabled coins: {\" \".join(coins)}')"
	@echo "✅ All coins validated successfully!"

# Preview pipeline execution without running
dry-run:
	@echo "🔍 Pipeline Dry-Run Preview"
	@echo ""
	@echo "📦 Coins to process: $(COINS)"
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

# Full pipeline: Bronze → Silver → Gold (all 10 coins)
pipeline: setup validate-coins
	@docker info >/dev/null 2>&1 || { echo "❌ Docker is not running!"; exit 1; }
	@echo "⚡ Running pipeline..."
	@echo ""
	@echo "📦 Bronze Layer: Ingesting raw data..."
	@for coin in $(COINS); do \
		uv run dg launch --assets 'raw/crypto_prices' --partition $$coin || exit 1; \
	done
	@echo ""
	@echo "🔄 Silver & Gold Layers: Running dbt transformations..."
	@uv run dg launch --assets 'staging/stg_crypto_prices,mart/fct_crypto_candlesticks' || exit 1
	@echo ""
	@echo "✅ Pipeline complete!"

# Single coin pipeline (usage: make coin=bitcoin pipeline-coin)
pipeline-coin: setup
ifndef coin
	@echo "❌ Error: coin parameter required. Usage: make coin=bitcoin pipeline-coin"
	@exit 1
endif
	@docker info >/dev/null 2>&1 || { echo "❌ Docker is not running!"; exit 1; }
	@echo "⚡ Running pipeline for $(coin)..."
	@echo ""
	@echo "📦 Bronze Layer: Ingesting raw data..."
	@uv run dg launch --assets 'raw/crypto_prices' --partition $(coin)
	@echo ""
	@echo "✅ Pipeline complete for $(coin)!"
	@echo ""
	@echo "💡 Note: dbt transformations run on full dataset. Run 'make pipeline' to process all coins."

# Launch Streamlit dashboard
dashboard:
	@test -f $(DB_PATH) || $(MAKE) pipeline
	@PYTHONPATH=. uv run streamlit run streamlit_dashboard/dashboard.py

# Launch FastAPI server
api:
	@test -f $(DB_PATH) || $(MAKE) pipeline
	@PYTHONPATH=. uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# One command to run everything
start: pipeline dashboard

# Launch Dagster development server
dev: setup
	@uv run dg dev

# Run tests
test: setup
	@uv run pytest tests/ -v

# Run tests with coverage
test-cov: setup
	@uv run pytest tests/ -v --cov=src/crypto_elt_pipeline --cov-report=term-missing

# Run type checking
typecheck: setup
	@uv run pyright src/crypto_elt_pipeline/

# Run linting and format checks
lint: setup
	@uv run ruff check src/ tests/
	@uv run ruff format --check src/ tests/

# Lint dbt models with SQLFluff
lint-dbt: setup
	@cd dbt_project && uv run sqlfluff lint models/

# Fix dbt linting issues with SQLFluff
lint-dbt-fix: setup
	@cd dbt_project && uv run sqlfluff fix models/

# Run dbt tests
test-dbt: setup
	@cd dbt_project && uv run dbt test

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

# Pipeline status - quick health check without opening Dagster UI
status:
	@echo "📊 Pipeline Status"
	@echo ""
	@if [ -f $(DB_PATH) ]; then \
		db_size=$$(du -h $(DB_PATH) | cut -f1); \
		echo "✅ Database exists: $(DB_PATH)"; \
		echo "📦 Database size: $$db_size"; \
		echo ""; \
		if command -v duckdb >/dev/null 2>&1; then \
			echo "📈 Record counts (Bronze Layer):"; \
			uv run python -c "import duckdb; conn = duckdb.connect('$(DB_PATH)', read_only=True); coins = conn.execute('SELECT DISTINCT coin FROM raw.crypto_prices ORDER BY coin').fetchall(); [print(f'  - {coin[0]}: {conn.execute(\"SELECT COUNT(*) FROM raw.crypto_prices WHERE coin = '\" + coin[0] + \"'\").fetchone()[0]:,} records') for coin in coins]"; \
			echo ""; \
			echo "📊 Latest data per coin:"; \
			uv run python -c "import duckdb, pendulum; conn = duckdb.connect('$(DB_PATH)', read_only=True); coins = conn.execute('SELECT DISTINCT coin FROM raw.crypto_prices ORDER BY coin').fetchall(); now = pendulum.now('UTC'); [print(f'  - {coin[0]}: {conn.execute(\"SELECT MAX(recorded_at) FROM raw.crypto_prices WHERE coin = '\" + coin[0] + \"'\").fetchone()[0]} (age: {(now - pendulum.instance(conn.execute(\"SELECT MAX(recorded_at) FROM raw.crypto_prices WHERE coin = '\" + coin[0] + \"'\").fetchone()[0])).in_words()})') for coin in coins]"; \
		else \
			echo "⚠️  duckdb CLI not installed. Install with: brew install duckdb"; \
		fi; \
	else \
		echo "❌ Database not found: $(DB_PATH)"; \
		echo "💡 Run 'make pipeline' to create the database"; \
	fi

.DEFAULT_GOAL := help
