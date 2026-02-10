.PHONY: help status orchestrate pipeline dashboard start clean clean-all

# --- CONFIGURATION ---
# Dynamically find the absolute path of this project to satisfy Dagster's requirement
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
export DAGSTER_HOME := $(PROJECT_ROOT)/.dagster_home

DASHBOARD_PATH = streamlit_dashboard/dashboard.py
DB_PATH = data/crypto.duckdb
DATA_DIR = data
VENV_SENTINEL = .venv/.setup_done

# --- MAIN TARGETS ---
help:
	@echo "₿ Bitcoin Analysis Pipeline"
	@echo "===================================="
	@echo "🚀 Main Commands:"
	@echo "  make start       → Full automated run (Setup + Pipeline + Dashboard)"
	@echo "  make dashboard   → Launch Streamlit Dashboard"
	@echo "  make clean       → Clean temporary files"
	@echo ""
	@echo "🛠️  Dev Commands:"
	@echo "  make orchestrate → Open Dagster UI"
	@echo "  make pipeline    → Run data pipeline"
	@echo "  make status      → Check system health"

# Smart Setup: Ensures DAGSTER_HOME and VENV exist
$(VENV_SENTINEL): pyproject.toml
	@echo "📦 Syncing environment and dependencies..."
	@uv sync
	@mkdir -p $(DATA_DIR) $(DAGSTER_HOME)
	@touch $(VENV_SENTINEL)

setup: $(VENV_SENTINEL)

status:
	@echo "🔍 System Status:"
	@test -d .venv && echo "  ✓ Environment ready" || echo "  ✗ Run 'make setup'"
	@test -d $(DAGSTER_HOME) && echo "  ✓ Dagster Home exists" || echo "  ⚠ No Dagster Home"
	@test -f $(DB_PATH) && echo "  ✓ Database exists" || echo "  ⚠ No data yet"

orchestrate: setup
	@echo "🐙 Dagster UI → http://localhost:3000 (Home: $(DAGSTER_HOME))"
	@mkdir -p $(DAGSTER_HOME)
	@uv run dg dev

pipeline: setup
	@echo "⚡ Running pipeline..."
	@mkdir -p $(DAGSTER_HOME)
	@uv run dg launch --assets '*'

dashboard:
	@if [ ! -f "$(DB_PATH)" ]; then \
		echo "❌ Error: Database not found. Running pipeline first..."; \
		$(MAKE) pipeline; \
	fi
	@echo "📊 Dashboard → http://localhost:8501"
	@uv run streamlit run $(DASHBOARD_PATH)

start:
	@echo "🚀 Starting Full Stack..."
	@$(MAKE) setup
	@$(MAKE) pipeline
	@echo "✅ Pipeline complete. Launching dashboard..."
	@$(MAKE) dashboard

# --- CLEANUP ---
clean:
	@echo "🧹 Cleaning temporary files..."
	@rm -rf dbt_project/target/ dbt_project/logs/ .dg/ .tmp*
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-all: clean
	@echo "🗑️  Full reset: removing database, venv, and Dagster history..."
	@rm -f $(DB_PATH) $(DB_PATH).wal $(VENV_SENTINEL)
	@rm -rf .venv/ $(DAGSTER_HOME)

.DEFAULT_GOAL := help