.PHONY: help setup start pipeline pipeline-coin dev dashboard test test-cov lint lint-dbt lint-dbt-fix clean deep-clean

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
	@echo "  make start     → Setup + Pipeline + Dashboard"
	@echo "  make setup     → Install dependencies and create directories"
	@echo "  make pipeline  → Run data pipeline (all enabled coins)"
	@echo "  make coin=bitcoin pipeline-coin → Run pipeline for specific coin"
	@echo "  make dev       → Launch Dagster development server"
	@echo "  make dashboard → Launch Streamlit Dashboard"
	@echo "  make test      → Run tests"
	@echo "  make test-cov  → Run tests with coverage report"
	@echo "  make lint      → Run linting and format checks"
	@echo "  make lint-dbt  → Lint dbt models with SQLFluff"
	@echo "  make lint-dbt-fix → Fix dbt linting issues"
	@echo "  make clean     → Clean database and dbt target (preserves history)"
	@echo "  make deep-clean → Full clean including .venv and .dagster_home"
	@echo ""
	@echo "  make list-coins    → Show all enabled coins from config"
	@echo "  make validate-coins → Validate coin list against config"

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

# List all enabled coins from config
list-coins:
	@echo "Available coins (from config/coins.yaml):"
	@uv run python -c "import yaml; [print(f'  - {c[\"id\"]} ({c[\"name\"]})') for c in yaml.safe_load(open('config/coins.yaml'))['coins'] if c.get('enabled', True)]"

# Full pipeline: Bronze → Silver → Gold (all 10 coins)
pipeline: setup validate-coins
	@docker info >/dev/null 2>&1 || { echo "❌ Docker is not running!"; exit 1; }
	@echo "⚡ Running pipeline (all enabled coins)..."
	@echo ""
	@echo "📦 Bronze Layer: Ingesting raw data..."
	@for coin in $(COINS); do \
		echo "  Processing $$coin..."; \
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
	@echo "🔄 Silver & Gold Layers: Running dbt transformations..."
	@uv run dg launch --assets 'staging/stg_crypto_prices,mart/fct_crypto_candlesticks'
	@echo ""
	@echo "✅ Pipeline complete for $(coin)!"

# Launch Streamlit dashboard
dashboard:
	@test -f $(DB_PATH) || $(MAKE) pipeline
	@uv run streamlit run streamlit_dashboard/dashboard.py

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

# Clean generated files (preserves .dagster_home for run history)
clean:
	@rm -rf data/*.duckdb data/*.duckdb.wal dbt_project/target
	@rm -rf source-* /tmp/airbyte
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Deep clean (including .dagster_home and .venv)
deep-clean:
	@rm -rf data/*.duckdb data/*.duckdb.wal .dagster_home dbt_project/target .venv
	@rm -rf source-* /tmp/airbyte
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

.DEFAULT_GOAL := help
