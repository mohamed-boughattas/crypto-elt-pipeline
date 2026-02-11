# 📐 Architecture

Technical architecture of the Bitcoin Analysis Pipeline.

---

## 🎯 System Overview

Modern ELT pipeline demonstrating:

- **PyAirbyte**: Code-first data extraction
- **Dagster**: Asset-based orchestration  
- **dbt**: Medallion architecture transformations
- **DuckDB + Polars**: Embedded analytics with high-performance DataFrames
- **Streamlit**: Interactive visualization

---

## 🏗️ Architecture Diagram

```text
┌─────────────────┐
│  CoinGecko API  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PyAirbyte     │ ◄── Extraction
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DuckDB (Bronze) │ ◄── Raw data
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  dbt (Silver)   │ ◄── Cleaned & typed
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  dbt (Gold)     │ ◄── Business metrics
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Streamlit     │ ◄── Visualization
└─────────────────┘

     Orchestrated by
    ┌───────────┐
    │  Dagster  │
    └───────────┘
```

---

## 📦 Components

### 1. Extraction: PyAirbyte

**Purpose**: Fetch Bitcoin data from CoinGecko API

**Key code:**

```python
source = ab.get_source(
    "source-coingecko-coins",
    config={"coin_id": "bitcoin", "vs_currency": "usd"},
    install_root=str(AIRBYTE_CACHE_DIR)
)
records = list(source.get_records("market_chart"))
```

**Why PyAirbyte?**

- No Docker/server infrastructure needed
- Battle-tested Airbyte connectors
- Built-in error handling and retries
- Schema validation included

---

### 2. Orchestration: Dagster

**Purpose**: Asset-based workflow with data lineage

**Asset graph:**

```text
source_coingecko_api
    ↓
bitcoin_prices (bronze)
    ↓
stg_bitcoin_prices (silver)
    ↓
fct_daily_btc_candlesticks (gold)
    ↓
streamlit_dashboard
```

**Why Dagster over Airflow?**

- Asset-centric (focus on "what to build" not "what to do")
- Automatic lineage tracking
- Built-in testing support
- Native Python development (no Docker needed)

---

### 3. Transformation: dbt + Medallion Architecture

#### Bronze Layer: `raw.bitcoin_prices`

- Immutable landing zone
- Raw API data, no transformations
- Append-only with deduplication

#### Silver Layer: `staging.stg_bitcoin_prices`

- Data cleaning and typing
- Quality tests (not-null, unique)
- Timestamp normalization

```sql
select
    cast(timestamp as timestamp) as timestamp,
    round(cast(price as double), 8) as price,
    round(cast(market_cap as double), 2) as market_cap
from {{ source('raw', 'bitcoin_prices') }}
where price > 0 and timestamp is not null
```

#### Gold Layer: `mart.fct_daily_btc_candlesticks` (Incremental)

- Business-ready OHLC metrics
- Daily aggregations
- Incremental processing (100x faster)

```sql
select
    date_trunc('day', timestamp) as date_day,
    arg_min(price, timestamp) as open_price,
    max(price) as high_price,
    min(price) as low_price,
    arg_max(price, timestamp) as close_price,
    sum(volume) as daily_volume,
    round(((max(price) - min(price)) / min(price)) * 100, 2) as volatility_pct
from {{ ref('stg_bitcoin_prices') }}
{% if is_incremental() %}
    where date_trunc('day', timestamp) >= (select max(date_day) from {{ this }})
{% endif %}
group by 1
```

**Incremental strategy:**

- First run: Process all historical data
- Subsequent runs: Only process new days
- Always re-processes current day for intra-day updates

---

### 4. Storage: DuckDB + Polars

**DuckDB:**

- Embedded OLAP database (no server setup)
- Columnar storage optimized for analytics
- Fast aggregations (perfect for OHLC calculations)
- Single-file database

**Polars I/O Manager:**

- 5-10x faster than Pandas
- Zero-copy reads from DuckDB
- Lazy evaluation for query optimization
- Multi-threading support

**Integration:**

```python
database_io_manager = DuckDBPolarsIOManager(
    database=str(DUCKDB_PATH)
)

@dg.asset(io_manager_key="io_manager")
def my_asset() -> pl.DataFrame:
    return pl.DataFrame(...)  # Automatically saved to DuckDB
```

---

### 5. Visualization: Streamlit

**Purpose**: Interactive dashboard querying Gold layer

```python
conn = duckdb.connect('data/crypto.duckdb')
df = conn.execute("SELECT * FROM mart.fct_daily_btc_candlesticks").pl()

fig = go.Figure(data=[go.Candlestick(
    x=df['date_day'],
    open=df['open_price'],
    high=df['high_price'],
    low=df['low_price'],
    close=df['close_price']
)])
```

**Features:**

- Real-time price tracking
- Interactive OHLC charts
- Volume analysis
- Volatility metrics

---

## 🔄 Data Flow

1. **Trigger**: User runs `make pipeline`
2. **Extract**: PyAirbyte fetches CoinGecko data → validates schema
3. **Load**: Polars I/O Manager writes to DuckDB Bronze (`raw.bitcoin_prices`)
4. **Transform Silver**: dbt runs `stg_bitcoin_prices` → cleans & types data
5. **Transform Gold**: dbt runs `fct_daily_btc_candlesticks` → calculates OHLC (incremental)
6. **Visualize**: Streamlit queries Gold layer → renders dashboard

---

## 🎯 Technology Choices

### PyAirbyte vs. Custom API Code

✅ **PyAirbyte**: Battle-tested, error handling, schema validation  
❌ Custom code: Need to implement retries, validation, rate limiting

### Dagster vs. Airflow

✅ **Dagster**: Asset-centric, auto lineage, native Python  
❌ Airflow: Task-centric, manual lineage, Docker setup

### dbt vs. Python Transformations

✅ **dbt**: SQL-based, built-in tests, incremental strategies  
❌ Python: Less accessible, manual testing, no auto-docs

### DuckDB vs. PostgreSQL

✅ **DuckDB**: Zero setup, columnar storage, fast aggregations  
✅ **PostgreSQL**: Better for multi-user production (migration path available)

---

## 📊 Performance Optimizations

### 1. Incremental Materialization

**Impact**: 100x faster daily refreshes

| Scenario      | Full Refresh | Incremental |
|---------------|--------------|-------------|
| 1 year data   | 60 seconds   | 0.5 seconds |
| 5 years data  | 5 minutes    | 0.5 seconds |

### 2. Polars Over Pandas

**Impact**: 5-10x faster DataFrame operations

| Operation | Pandas | Polars |
| ----------- | -------- | -------- |
| CSV read (1GB) | 12s | 2s |
| GroupBy | 8s | 0.8s |
| Join (1M rows) | 5s | 0.5s |

### 3. DuckDB Columnar Storage

- Only reads needed columns
- Vectorized execution (SIMD)
- Parallel query execution

### 4. PyAirbyte Workspace Management

- Connector cache in `.airbyte_cache/`
- Working directory isolation
- Clean project root

---

## 📈 Scalability Path

**Current (Local Dev)**:

- 1-10M rows
- < 10GB storage
- Single user

**Medium Scale**:

- Keep DuckDB
- Single cloud server
- Scheduled runs

**Large Scale**:

- Migrate to PostgreSQL/Snowflake
- Distributed dbt execution
- Kubernetes deployment

---

## 🔍 Database Structure

```text
crypto.duckdb
├── raw (Bronze)
│   └── bitcoin_prices
├── staging (Silver)
│   └── stg_bitcoin_prices
└── mart (Gold)
    └── fct_daily_btc_candlesticks
```

---

## 📚 Related Documentation

- [Data Modeling](data-modeling.md) - Deep dive into Medallion layers
- [Setup Guide](setup-guide.md) - Installation and configuration

---

**[← Back to Documentation Index](README.md)**
