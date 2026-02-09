.PHONY: help setup orchestrate pipeline dashboard start

# --- CONFIGURATION ---
DASHBOARD_PATH = streamlit_dashboard/dashboard.py
DB_PATH = data/crypto.duckdb

# --- COMMANDS ---

help:
	@echo "₿  Bitcoin Market Intelligence Stack"
	@echo "===================================="
	@echo "1. make setup      : 📦 Install dependencies"
	@echo "2. make orchestrate: 🐙 Start Dagster UI (To run via 'Materialize All')"
	@echo "3. make pipeline   : ⚡ Run pipeline via CLI (dg launch)"
	@echo "4. make dashboard  : 📊 Launch the Streamlit Dashboard"
	@echo "5. make start      : 🚀 Full Automated Run (Setup -> Launch -> UI)"

setup:
	@echo "📦 Syncing project dependencies..."
	uv sync

orchestrate:
	@echo "🐙 Launching Dagster UI at http://localhost:3000..."
	uv run dg dev

pipeline:
	@echo "⚡ Launching materialization run via CLI..."
	uv run dg launch --assets '*'

check-db:
	@if [ ! -f "$(DB_PATH)" ]; then \
		echo "❌ ERROR: Database not found. Run 'make pipeline' or use the Dagster UI."; \
		exit 1; \
	fi

dashboard: check-db
	@echo "📊 Launching Bitcoin Market Dashboard..."
	uv run streamlit run $(DASHBOARD_PATH)

# Fully automated method (No UI interaction required)
start:
	@echo "🚀 Starting Automated Pipeline..."
	make setup
	make pipeline
	@echo "📊 Data generated. Launching Dashboard..."
	make dashboard