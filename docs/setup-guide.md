# 🚀 Setup Guide

Complete installation and configuration guide for the Crypto ELT Pipeline.

---

## 📋 Prerequisites

### Required Software

| Software   | Version | Purpose                             |
| ---------- | ------- | ----------------------------------- |
| **Python** | 3.10+   | Runtime environment                 |
| **uv**     | Any     | Package manager                     |
| **Docker** | Any     | Required for PyAirbyte connectors   |
| **Git**    | Any     | Version control                     |

> **Docker must be running before executing any pipeline commands.**
>
> PyAirbyte uses Docker containers to run data extraction connectors. If Docker is not running, the pipeline will fail with a connection error.

### Optional: CoinGecko Pro API

The pipeline uses the free CoinGecko API by default (10-50 calls/minute). For higher rate limits (500+ calls/minute), you can optionally use a Pro API key:

1. Get your API key at: [CoinGecko API Pricing](https://www.coingecko.com/en/api/pricing)
2. Create a `.env` file in the project root:

   ```bash
   cp .env.example .env
   ```

3. Add your API key to `.env`:

   ```text
   COINGECKO_API_KEY=your_api_key_here
   ```

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

**Verify installation:**

```bash
# Check that virtual environment was created
ls -la .venv
```

---

### Step 4: Start Docker

PyAirbyte connectors run in Docker containers. Ensure Docker is running:

```bash
# Check Docker status
docker info

# If not running, start Docker Desktop or Docker daemon
```

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

1. PyAirbyte fetches cryptocurrency data from CoinGecko API (10 coins: Bitcoin, Ethereum, XRP, Solana, Cardano, Avalanche, Polkadot, BNB, Chainlink, Dogecoin)
2. Raw data loads into DuckDB Bronze layer (`raw.crypto_prices`)
3. dbt runs Silver transformations (`staging.stg_crypto_prices`)
4. dbt runs Gold transformations (`mart.fct_crypto_candlesticks`)

**Expected output:**

```text
⚡ Running pipeline...
📦 Installing dependencies...
🦎 Initializing CoinGecko source connector
📊 Reading cryptocurrency market data
✅ Successfully ingested records to Bronze layer
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
uv run dg dev
```

**Access:**

- Open browser: <http://localhost:3000>
- Explore asset graph, lineage, and run history

**Features:**

- 📊 Visual asset dependency graph
- 🔍 Data lineage tracking
- 📝 Run logs and metadata
- 🎯 Manual asset materialization
- ⏰ Automated schedules (daily refresh at 6 AM UTC)

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
crypto_elt_pipeline:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ../data/crypto.duckdb
      threads: 4
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

-- Check Bronze layer (all coins)
SELECT coin, COUNT(*) FROM raw.crypto_prices GROUP BY coin;

-- Check Silver layer
SELECT COUNT(*) FROM staging.stg_crypto_prices;

-- Check Gold layer
SELECT coin, COUNT(*) FROM mart.fct_crypto_candlesticks GROUP BY coin;

-- View latest data
SELECT * FROM mart.fct_crypto_candlesticks
ORDER BY trade_date DESC
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
Running with dbt=1.11.3
Found 2 models, 46 data tests, 1 source, 871 macros
Completed successfully
Done. PASS=46 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=46
```

---

### 3. Check Project Status

```bash
# Check database exists
ls -lh data/crypto.duckdb

# Verify Dagster home is configured
ls -la .dagster_home
```

---

## 🧪 Running Tests

The project includes a comprehensive test suite for validating core functionality with **91 tests** covering data quality, transformations, and integration scenarios.

### Run All Tests

```bash
make test
```

### Run with Coverage

```bash
make test-cov
```

### Expected Output

```text
============================= test session starts ==============================
collected 91 items

tests/test_config.py::TestConfig::test_load_config_exists PASSED
tests/test_config.py::TestConfig::test_get_config_returns_config PASSED
tests/test_config.py::TestConfig::test_config_has_coins PASSED
tests/test_config.py::TestConfig::test_config_has_api_settings PASSED
tests/test_config.py::TestConfig::test_config_has_ingestion_settings PASSED
tests/test_config.py::TestConfig::test_config_has_monitoring_settings PASSED
tests/test_config.py::TestConfig::test_config_has_database_settings PASSED
tests/test_config.py::TestConfig::test_config_has_api_docker_settings PASSED
tests/test_config.py::TestConfig::test_config_has_retry_settings PASSED
tests/test_config.py::TestConfig::test_config_has_pipeline_settings PASSED
tests/test_config.py::TestConfigCoins::test_coins_have_required_fields PASSED
tests/test_config.py::TestConfigCoins::test_enabled_coins_filter PASSED
tests/test_config.py::TestConfigCoins::test_coin_ids_list PASSED
tests/test_config.py::TestConfigCoins::test_coin_colors_mapping PASSED
tests/test_config.py::TestConfigCoins::test_enabled_coin_ids PASSED
tests/test_config.py::TestConstants::test_duckdb_path_is_defined PASSED
tests/test_config.py::TestConstants::test_duckdb_path_has_correct_name PASSED
tests/test_config.py::TestConstants::test_duckdb_path_in_data_directory PASSED
tests/test_config.py::TestConstants::test_project_root_is_defined PASSED
tests/test_config.py::TestConstants::test_project_root_exists PASSED
tests/test_crypto_db.py::TestGetLatestTimestamp::test_returns_latest_timestamp PASSED
tests/test_crypto_db.py::TestGetLatestTimestamp::test_returns_none_when_no_data PASSED
tests/test_crypto_db.py::TestGetLatestTimestamp::test_calculate_days_to_fetch_logic PASSED
tests/test_crypto_db.py::TestGetExistingData::test_returns_dataframe_schema PASSED
tests/test_crypto_db.py::TestGetExistingData::test_returns_empty_for_missing_data PASSED
tests/test_crypto_db.py::TestCalculateDaysToFetch::test_returns_default_when_none_timestamp PASSED
tests/test_crypto_db.py::TestCalculateDaysToFetch::test_returns_minimum_one_day PASSED
tests/test_crypto_db.py::TestCalculateDaysToFetch::test_returns_correct_days_difference PASSED
tests/test_crypto_db.py::TestCalculateDaysToFetch::test_caps_at_default_days PASSED
tests/test_crypto_db.py::TestCalculateDaysToFetch::test_handles_zero_days_ago PASSED
tests/test_crypto_db.py::TestCalculateDaysToFetch::test_custom_default_days PASSED
tests/test_data_quality.py::TestDataIntegrity::test_data_integrity_constraints PASSED
tests/test_data_quality.py::TestDataIntegrity::test_ohlc_consistency PASSED
tests/test_data_quality.py::TestDataIntegrity::test_temporal_data_quality PASSED
tests/test_data_quality.py::TestBusinessRules::test_positive_prices PASSED
tests/test_data_quality.py::TestBusinessRules::test_positive_market_cap PASSED
tests/test_data_quality.py::TestBusinessRules::test_positive_volume PASSED
tests/test_data_quality.py::TestBusinessRules::test_data_completeness PASSED
tests/test_data_quality.py::TestSchemaValidation::test_raw_schema_validation PASSED
tests/test_data_quality.py::TestSchemaValidation::test_enhanced_schema_validation PASSED
tests/test_data_quality.py::TestSchemaValidation::test_negative_price_fails_validation PASSED
tests/test_schemas.py::TestRawMarketChartSchema::test_valid_raw_data_passes PASSED
tests/test_schemas.py::TestRawMarketChartSchema::test_missing_prices_column_fails PASSED
tests/test_schemas.py::TestRawMarketChartSchema::test_missing_market_caps_column_fails PASSED
tests/test_schemas.py::TestRawMarketChartSchema::test_missing_total_volumes_column_fails PASSED
tests/test_schemas.py::TestRawMarketChartSchema::test_extra_columns_allowed PASSED
tests/test_schemas.py::TestRawMarketChartSchema::test_empty_dataframe_passes PASSED
tests/test_schemas.py::TestEnhancedMarketSchema::test_valid_flattened_data_passes PASSED
tests/test_schemas.py::TestEnhancedMarketSchema::test_missing_coin_column_fails PASSED
tests/test_schemas.py::TestEnhancedMarketSchema::test_missing_price_column_fails PASSED
tests/test_schemas.py::TestEnhancedMarketSchema::test_negative_price_fails PASSED
tests/test_schemas.py::TestEnhancedMarketSchema::test_zero_volume_passes PASSED
tests/test_schemas.py::TestEnhancedMarketSchema::test_extra_columns_allowed PASSED
tests/test_transform.py::TestUnnestMarketData::test_empty_raw_data PASSED
tests/test_transform.py::TestUnnestMarketData::test_single_data_point PASSED
tests/test_transform.py::TestUnnestMarketData::test_multiple_data_points PASSED
tests/test_transform.py::TestUnnestMarketData::test_different_coins PASSED
tests/test_transform.py::TestUnnestMarketData::test_different_currency PASSED
tests/test_transform.py::TestResampleToHourly::test_empty_dataframe PASSED
tests/test_transform.py::TestResampleToHourly::test_single_hour PASSED
tests/test_transform.py::TestResampleToHourly::test_multiple_hours PASSED
tests/test_transform.py::TestResampleToHourly::test_resample_5min_to_hourly PASSED
tests/test_transform.py::TestResampleToHourly::test_uses_last_price PASSED
tests/test_transform.py::TestMergeData::test_empty_existing PASSED
tests/test_transform.py::TestMergeData::test_empty_new PASSED
tests/test_transform.py::TestMergeData::test_deduplication PASSED
tests/test_transform.py::TestMergeData::test_concatenation PASSED
tests/test_transform.py::TestSchemaValidation::test_raw_schema_valid PASSED
tests/test_api.py::TestAPIEndpoints::test_health_check_success PASSED
tests/test_api.py::TestAPIEndpoints::test_health_check_database_not_found PASSED
tests/test_api.py::TestAPIEndpoints::test_health_check_database_connection_failed PASSED
tests/test_api.py::TestAPIEndpoints::test_list_coins_success PASSED
tests/test_api.py::TestAPIEndpoints::test_list_coins_empty PASSED
tests/test_api.py::TestAPIEndpoints::test_list_coins_database_error PASSED
tests/test_api.py::TestAPIEndpoints::test_get_candlesticks_success PASSED
tests/test_api.py::TestAPIEndpoints::test_get_candlesticks_with_date_filters PASSED
tests/test_api.py::TestAPIEndpoints::test_get_candlesticks_with_days_limit PASSED
tests/test_api.py::TestAPIEndpoints::test_get_candlesticks_invalid_days_parameter PASSED
tests/test_api.py::TestAPIEndpoints::test_get_candlesticks_coin_not_found PASSED
tests/test_api.py::TestAPIEndpoints::test_get_candlesticks_database_error PASSED
tests/test_api.py::TestAPIEndpoints::test_get_latest_data_success PASSED
tests/test_api.py::TestAPIEndpoints::test_get_latest_data_empty PASSED
tests/test_api.py::TestAPIEndpoints::test_get_latest_data_database_error PASSED
tests/test_api.py::TestAPIEndpoints::test_root_endpoint PASSED
tests/test_api.py::TestAPIEndpoints::test_cors_headers PASSED
tests/test_api.py::TestAPIEndpoints::test_openapi_documentation PASSED
tests/test_api.py::TestAPIEndpoints::test_redoc_documentation PASSED
tests/test_api.py::TestAPIValidation::test_get_candlesticks_invalid_date_format PASSED
tests/test_api.py::TestAPIValidation::test_get_candlesticks_negative_days PASSED
tests/test_api.py::TestAPIValidation::test_get_candlesticks_zero_days PASSED
tests/test_api.py::TestAPIErrorHandling::test_database_connection_error_handling PASSED

======================= 91 passed in 9.16s =======================
```

### Test Categories

- **Configuration Tests (23)**: Path validation, project structure, and configuration loading
- **Schema Tests (11)**: Pandera validation for raw and enhanced data contracts
- **Ingestion Tests (17)**: Data transformations, incremental loading, merging, and resampling
- **Data Quality Tests (8)**: OHLC consistency and business logic validation
- **Database Tests (9)**: DuckDB operations, timestamp retrieval, and data fetching

> **Detailed testing guide:** See [Testing Guide](testing.md)

## 🔧 Code Quality Tools

### SQL Formatting with SQLFluff

**Purpose**: Consistent SQL formatting and linting for dbt models

**Configuration**: `dbt_project/.sqlfluff`

```ini
[sqlfluff]
dialect = duckdb
max_line_length = 120
ignore = templating, parsing

[sqlfluff:rules]
comma_style = trailing
single_table_references = qualified
```

**Usage:**

```bash
# Check SQL formatting
cd dbt_project
uv run sqlfluff lint models/

# Auto-fix formatting issues
uv run sqlfluff fix models/

# Check specific file
uv run sqlfluff lint models/marts/fct_crypto_candlesticks.sql
```

**Current Status:**

- ✅ 0 SQLFluff warnings
- ✅ DuckDB-compatible linting rules
- ✅ 120 character line length
- ✅ Trailing comma style

**Integration:**

- Automated formatting in CI/CD pipeline
- DuckDB-specific dialect configuration
- Templating and parsing warnings ignored for dbt compatibility

---

## 🧹 Cleanup Commands

```bash
# Clean temporary files (keeps database)
make clean

# Full cleanup (removes database too)
make clean-all

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
mkdir -p data .dagster_home
# Run pipeline for each partition (10 cryptocurrencies)
for coin in bitcoin ethereum ripple solana cardano avalanche-2 polkadot binancecoin chainlink dogecoin; do
    uv run dg launch --assets 'raw/crypto_prices' --partition "$coin"
done
uv run dbt run --project-dir dbt_project
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

**Solution 2**: Check API limits

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
4. **Read architecture**: See [Architecture Documentation](system-design.md)
5. **Understand data models**: See [Data Modeling Guide](data-modeling.md)

---

## 📚 Useful Commands

```bash
# Run full pipeline
make start

# Run pipeline only (no dashboard)
make pipeline

# Open Dagster UI
make dev

# Open dashboard
make dashboard

# Run dbt tests
cd dbt_project && uv run dbt test

# Generate dbt Docs
cd dbt_project && uv run dbt docs generate && uv run dbt docs serve

# Clean temporary files
make clean

# Full cleanup
make deep-clean
```

---

## 📖 Related Documentation

- [Architecture](system-design.md) - System design and components
- [Data Modeling](data-modeling.md) - Medallion architecture details
- [Testing Guide](testing.md) - Testing strategy and coverage

---

**[← Back to Documentation Index](index.md)**
