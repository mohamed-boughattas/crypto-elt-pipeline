# 🚀 Setup Guide

Complete installation and configuration guide for the Bitcoin Analysis Pipeline.

---

## 📋 Prerequisites

### Required Software

| Software | Version | Purpose |
| ---------- | --------- | --------- |
| **Python** | 3.10+ | Runtime environment |
| **uv** | Latest | Package manager |
| **Git** | Any | Version control |

### System Requirements

- **OS**: macOS, Linux, or Windows (WSL recommended)
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 2GB free space

---

## 🔧 Installation

### Step 1: Install uv (Package Manager)

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify installation:**

```bash
uv --version
```

---

### Step 2: Clone the Repository

```bash
# Clone the project
git clone https://github.com/mohamed-boughattas/crypto-elt-pipeline.git
cd crypto-elt-pipeline

# Verify structure
ls -la
```

**Expected structure:**

```text
crypto-elt-pipeline/
├── src/
├── dbt_project/
├── streamlit_dashboard/
├── Makefile
├── pyproject.toml
└── README.md
```

---

### Step 3: Install Dependencies

```bash
# Create virtual environment and install dependencies
make setup
```

**What this does:**

1. Creates `.venv/` virtual environment
2. Installs Python packages from `pyproject.toml`
3. Creates `data/` directory for DuckDB
4. Creates `.dagster_home/` for Dagster metadata
5. Creates `.airbyte_cache/` for PyAirbyte connectors

**Verify installation:**

```bash
make status
```

**Expected output:**

```text
✓ uv installed
✓ Virtual environment ready
✓ Dagster home configured
✓ Port 3000 available (Dagster)
✓ Port 8501 available (Streamlit)
```

---

### Step 4: Install dbt Packages

```bash
make install
```

**What this does:**

- Installs dbt dependencies
- Downloads dbt packages to `dbt_project/dbt_packages/`

---

## ⚡ Quick Start (Automated)

**Run everything with one command:**

```bash
make start
```

**This will:**

1. ✅ Setup environment
2. ✅ Run data pipeline (extract → transform → load)
3. ✅ Launch Streamlit dashboard

**Access the dashboard:**

- Open browser: <http://localhost:8501>

---

## 🔄 Manual Workflow

If you prefer step-by-step execution:

### 1. Run Data Pipeline

```bash
make pipeline
```

**What happens:**

1. PyAirbyte fetches Bitcoin data from CoinGecko API
2. Raw data loads into DuckDB Bronze layer (`raw.bitcoin_prices`)
3. dbt runs Silver transformations (`staging.stg_bitcoin_prices`)
4. dbt runs Gold transformations (`mart.fct_daily_btc_candlesticks`)

**Expected output:**

```text
⚡ Running pipeline...
📦 Installing dependencies...
🦎 Initializing CoinGecko source connector
📊 Reading Bitcoin market data
✅ Successfully ingested 1008 records to Bronze layer
✅ Processing nested lists...
✅ Final output validation passed
✅ Running dbt transformations...
✅ Pipeline complete
```

**Verify database:**

```bash
# Check database exists
ls -lh data/crypto.duckdb

# Query from command line
make pipeline
```

---

### 2. Launch Dagster UI (Optional)

```bash
make orchestrate
```

**Access:**

- Open browser: <http://localhost:3000>
- Explore asset graph, lineage, and run history

**Features:**

- 📊 Visual asset dependency graph
- 🔍 Data lineage tracking
- 📝 Run logs and metadata
- 🎯 Manual asset materialization

---

### 3. Launch Streamlit Dashboard

```bash
make dashboard
```

**Access:**

- Open browser: <http://localhost:8501>

**Dashboard features:**

- 💰 Real-time Bitcoin price
- 📈 OHLC candlestick charts
- 📊 Volume analysis
- 📉 Volatility metrics
- 📅 Date range filtering

---

## 🛠️ Configuration

### Environment Variables

Create `.env` file (optional):

```bash
# .env
DAGSTER_HOME=/absolute/path/to/.dagster_home
COINGECKO_API_KEY=your_api_key_here  # Optional (free tier works)
```

**Note**: Free tier CoinGecko API has no key requirement.

---

### Dagster Configuration

**File**: `.dagster_home/dagster.yaml`

```yaml
# Disable telemetry
telemetry:
  enabled: false
```

**Already configured** - no changes needed.

---

### dbt Configuration

**File**: `dbt_project/profiles.yml`

```yaml
crypto_elt:
  outputs:
    dev:
      type: duckdb
      path: ../data/crypto.duckdb
      schema: main
  target: dev
```

**Already configured** - uses relative path to DuckDB file.

---

## ✅ Verification Steps

### 1. Check Database Tables

```bash
# Open DuckDB CLI
cd data
duckdb crypto.duckdb
```

```sql
-- List all schemas
SHOW SCHEMAS;

-- Check Bronze layer
SELECT COUNT(*) FROM raw.bitcoin_prices;

-- Check Silver layer
SELECT COUNT(*) FROM staging.stg_bitcoin_prices;

-- Check Gold layer
SELECT COUNT(*) FROM mart.fct_daily_btc_candlesticks;

-- View latest data
SELECT * FROM mart.fct_daily_btc_candlesticks 
ORDER BY date_day DESC 
LIMIT 5;

-- Exit
.quit
```

---

### 2. Test dbt Models

```bash
cd dbt_project
uv run dbt test
```

**Expected output:**

```text
Running with dbt=1.7.0
Found 2 models, 5 tests, 0 snapshots...
Completed successfully
```

---

### 3. Check Project Status

```bash
make status
```

**Healthy output:**

```text
✓ uv installed
✓ Virtual environment ready
✓ Dagster home configured
✓ Database exists (2.5MB)
✓ dbt packages installed
✓ Port 3000 available
✓ Port 8501 available
```

---

## 🧹 Cleanup Commands

```bash
# Clean temporary files (keeps database)
make clean

# Full cleanup (removes database too)
make clean-all

# Remove only PyAirbyte cache
rm -rf .airbyte_cache/

# Remove only Dagster metadata
rm -rf .dagster_home/

# Remove database
rm -rf data/
```

---

## 🔧 Troubleshooting

### Issue: `uv: command not found`

**Solution:**

```bash
# Re-run installation
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart terminal or source profile
source ~/.bashrc  # Linux
source ~/.zshrc   # macOS
```

---

### Issue: Port already in use

**Symptom:**

```text
❌ Port 3000 already in use
```

**Solution:**

```bash
# Find process using port
lsof -ti:3000

# Kill process
kill -9 $(lsof -ti:3000)

# Or use different port
uv run dg dev --port 3001
```

---

### Issue: `make: command not found`

**Solution:**

**macOS:**

```bash
xcode-select --install
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt-get install build-essential
```

**Alternative**: Run commands directly

```bash
uv sync
mkdir -p data .dagster_home .airbyte_cache
uv run dg launch --assets '*'
```

---

### Issue: PyAirbyte connector fails

**Symptom:**

```text
❌ Extraction failed: Connection error
```

**Solution 1**: Check internet connection

```bash
curl -I https://api.coingecko.com
```

**Solution 2**: Clear PyAirbyte cache

```bash
rm -rf .airbyte_cache/
make pipeline
```

**Solution 3**: Check API limits

- CoinGecko free tier: 10-50 calls/minute
- Wait a few minutes and retry

---

### Issue: DuckDB database locked

**Symptom:**

```text
❌ Database is locked
```

**Solution:**

```bash
# Close all connections (Dagster UI, DuckDB CLI, Streamlit)
# Then retry

# If persists, remove lock file
rm data/crypto.duckdb.wal
```

---

### Issue: dbt tests fail

**Symptom:**

```text
❌ Failure in test not_null_stg_bitcoin_prices_timestamp
```

**Solution:**

```bash
# Re-run pipeline to refresh data
make clean
make pipeline

# Run tests again
cd dbt_project
uv run dbt test
```

---

### Issue: Streamlit won't start

**Symptom:**

```text
❌ Error: Database not found
```

**Solution:**

```bash
# Ensure pipeline has run first
make pipeline

# Then launch dashboard
make dashboard
```

---

## 🎯 Next Steps

After successful setup:

1. **Explore the data**: Open Dagster UI and click through asset lineage
2. **View transformations**: Check `dbt_project/models/` SQL files
3. **Customize dashboard**: Edit `streamlit_dashboard/dashboard.py`
4. **Read architecture**: See [Architecture Documentation](system_design)
5. **Add features**: See [Development Guide](development.md)

---

## 📚 Useful Commands

```bash
# Check system status
make status

# Run full pipeline
make start

# Run pipeline only (no dashboard)
make pipeline

# Open Dagster UI
make orchestrate

# Open dashboard
make dashboard

# View pipeline logs
make logs

# Run dbt tests
cd dbt_project && uv run dbt test

# Generate dbt docs
cd dbt_project && uv run dbt docs generate && uv run dbt docs serve

# Clean temporary files
make clean

# Full cleanup
make clean-all
```

---

## 🆘 Getting Help

**Still having issues?**

1. Check [Troubleshooting Guide](troubleshooting.md)
2. Review [Architecture Documentation](system_design)
3. Open [GitHub Issue](https://github.com/mohamed-boughattas/crypto-elt-pipeline/issues)

---

## 📖 Related Documentation

- [Architecture](system_design) - System design and components
- [Data Modeling](data_modeling.md) - Medallion architecture details
- [Development Guide](development.md) - Adding features
- [Troubleshooting](troubleshooting.md) - Common issues

---

**[← Back to Documentation Index](README.md)**
