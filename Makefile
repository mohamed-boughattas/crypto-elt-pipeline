.PHONY: help setup status orchestrate pipeline dashboard start clean clean-all

# --- CONFIGURATION ---
DASHBOARD_PATH = streamlit_dashboard/dashboard.py
DB_PATH = data/crypto.duckdb
DATA_DIR = data

# --- COMMANDS ---

help:
	@echo "Bitcoin Analysis Pipeline"
	@echo "===================================="
	@echo ""
	@echo "🚀 Main Commands:"
	@echo "  make start       → Full automated run (Setup + Pipeline + Dashboard)"
	@echo "  make dashboard   → Launch Streamlit Dashboard"
	@echo "  make clean       → Clean temporary files"
	@echo ""
	@echo "🛠️  Dev Commands:"
	@echo "  make orchestrate → Open Dagster UI"
	@echo "  make pipeline    → Run data pipeline using CLI"
	@echo "  make status      → Check system health"
	@echo "  make clean-all   → Full cleanup (temporary files + database)"
	@echo ""

setup:
	@echo "📦 Installing dependencies..."
	@uv sync
	@mkdir -p $(DATA_DIR)

status:
	@echo "🔍 System Status:"
	@if [ -d ".venv" ]; then echo "  ✓ Environment ready"; else echo "  ✗ Run 'make setup'"; fi
	@if [ -f "$(DB_PATH)" ]; then echo "  ✓ Database exists"; else echo "  ⚠ No data yet"; fi
	@if [ -d "dbt_project/dbt_packages" ]; then echo "  ✓ dbt packages installed"; else echo "  ⚠ Run 'dbt deps'"; fi

orchestrate:
	@echo "🐙 Dagster UI → http://localhost:3000"
	@uv run dg dev

pipeline: setup
	@echo "⚡ Running pipeline..."
	@uv run dg launch --assets '*'

check-db:
	@if [ ! -f "$(DB_PATH)" ]; then \
		echo "❌ Error: Database not found. Run 'make start' or 'make pipeline' first."; \
		exit 1; \
	fi

dashboard: check-db
	@echo "📊 Dashboard → http://localhost:8501"
	@uv run streamlit run $(DASHBOARD_PATH)

start:
	@echo "🚀 Starting Full Stack..."
	@$(MAKE) setup
	@$(MAKE) pipeline
	@sleep 3
	@echo "✅ Data generated. Launching dashboard..."
	@$(MAKE) dashboard

clean:
	@echo "🧹 Cleaning temporary files..."
	@rm -rf dbt_project/target/ dbt_project/logs/
	@rm -rf .dagster/ .dg/ .tmp .tmp_* __pycache__/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-all: clean
	@echo "🗑️  Removing database..."
	@rm -f $(DB_PATH) $(DB_PATH).wal

.DEFAULT_GOAL := help