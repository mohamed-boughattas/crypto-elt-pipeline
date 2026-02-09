.PHONY: help status orchestrate pipeline dashboard start clean clean-all

# --- CONFIGURATION ---
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

# Smart Setup: Only triggers uv sync if pyproject.toml is newer than the sentinel
$(VENV_SENTINEL): pyproject.toml
	@echo "📦 Syncing environment and dependencies..."
	@uv sync
	@mkdir -p $(DATA_DIR)
	@touch $(VENV_SENTINEL)

setup: $(VENV_SENTINEL)

status:
	@echo "🔍 System Status:"
	@test -d .venv && echo "  ✓ Environment ready" || echo "  ✗ Run 'make setup'"
	@test -f $(DB_PATH) && echo "  ✓ Database exists" || echo "  ⚠ No data yet"

orchestrate: setup
	@echo "🐙 Dagster UI → http://localhost:3000"
	@uv run dg dev

pipeline: setup
	@echo "⚡ Running pipeline..."
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
	@rm -rf dbt_project/target/ dbt_project/logs/ .dagster/ .dg/ .tmp*
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-all: clean
	@echo "🗑️  Full reset: removing database and venv..."
	@rm -f $(DB_PATH) $(DB_PATH).wal $(VENV_SENTINEL)
	@rm -rf .venv/

.DEFAULT_GOAL := help