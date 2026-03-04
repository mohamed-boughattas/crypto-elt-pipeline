# 📐 Architecture

Technical architecture of the Crypto ELT Pipeline.

---

## 🎯 System Overview

Modern ELT pipeline demonstrating:

- **PyAirbyte**: Code-first data extraction
- **Dagster**: Asset-based orchestration with partitions
- **dbt**: Medallion architecture transformations
- **DuckDB + Polars**: Embedded analytics with high-performance DataFrames
- **Streamlit**: Interactive visualization

**Supported Cryptocurrencies:** Bitcoin, Ethereum, XRP, Solana, Cardano, Avalanche, Polkadot, BNB, Chainlink, Dogecoin (10 coins)

---

## 🏗️ Architecture Diagram

```text
┌─────────────────┐
│  CoinGecko API  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PyAirbyte     │ ◄── Extraction (partitioned by coin)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DuckDB (Bronze) │ ◄── Raw nested data (immutable)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  dbt (Silver)   │ ◄── Flatten & clean (SQL unnest)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  dbt (Gold)     │ ◄── OHLC candlesticks (table + SMAs)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Streamlit     │ ◄── Multi-coin dashboard
└─────────────────┘

     Orchestrated by
    ┌───────────┐
    │  Dagster  │
    └───────────┘
```

---

## 📦 Components

### 1. Extraction: PyAirbyte

**Purpose**: Fetch cryptocurrency data from CoinGecko API

**Key features:**

- **Incremental loading**: Fetches only new data since last timestamp
- **Hourly resampling**: Normalizes all data to consistent hourly granularity
- **Automatic deduplication**: Merges new data with existing records
- **Configurable retry**: Exponential backoff with jitter for rate limit handling
- **API key support**: Optional CoinGecko Pro API key for higher rate limits

**Configuration (`config/coins.yaml`):**

```yaml
ingestion:
  vs_currency: usd
  days_to_fetch: 30
  history_days: 365  # Days of historical data to load from DuckDB
  retry_max_attempts: 3
  retry_base_delay: 10  # seconds
  retry_max_delay: 60   # seconds
```

**Environment variables (`.env`):**

```bash
COINGECKO_API_KEY=your_api_key_here  # Optional
```

**Key code:**

```python
# Incremental loading: check existing data
latest_timestamp = get_latest_timestamp(coin_id)
days_to_fetch = calculate_days_to_fetch(latest_timestamp, default_days=30)

# Fetch only needed data
source = ab.get_source(
    "source-coingecko-coins",
    docker_image="airbyte/source-coingecko-coins:0.2.26",
    config={
        "coin_id": coin_id,  # bitcoin, ethereum, ripple, solana, cardano, avalanche-2, polkadot, binancecoin, chainlink, dogecoin
        "vs_currency": "usd",
        "days": str(days_to_fetch),
    },
    install_if_missing=True,
)
records = list(source.get_records("market_chart"))

# Resample to hourly granularity for consistency
final_df = resample_to_hourly(merged_df)
```

**Why PyAirbyte?**

- No Docker/server infrastructure needed
- Battle-tested Airbyte connectors
- Built-in error handling and retries
- Schema validation included

**API Granularity:**

| Days Requested | Granularity | After Resampling |
| -------------- | ----------- | ---------------- |
| 1 day          | 5-minute    | Hourly           |
| 2-90 days      | Hourly      | Hourly           |
| >90 days       | Daily       | Daily            |

---

### 2. Orchestration: Dagster

**Purpose**: Asset-based workflow with data lineage and partitioning

**Asset graph:**

```text
source_coingecko_api
    ↓
crypto_prices[bitcoin]      ─┐
crypto_prices[ethereum]     ─┤
crypto_prices[ripple]       ─┤
crypto_prices[solana]       ─┤
crypto_prices[cardano]      ─┼── Bronze (10 partitions)
crypto_prices[avalanche-2]  ─┤
crypto_prices[polkadot]     ─┤
crypto_prices[binancecoin]  ─┤
crypto_prices[chainlink]    ─┤
crypto_prices[dogecoin]     ─┘
    ↓
stg_crypto_prices (Silver)
    ↓
fct_crypto_candlesticks (Gold)
    ↓
streamlit_dashboard
```

**Partitioning Strategy:**

The pipeline uses Dagster's `StaticPartitionsDefinition` to process multiple cryptocurrencies in parallel:

```python
CRYPTO_PARTITIONS = dg.StaticPartitionsDefinition(
    ["bitcoin", "ethereum", "ripple", "solana", "cardano", "avalanche-2", "polkadot", "binancecoin", "chainlink", "dogecoin"]
)
```

**Why Dagster over Airflow?**

- Asset-centric (focus on "what to build" not "what to do")
- Automatic lineage tracking
- Built-in testing support
- Native Python development (no Docker needed)
- First-class partitioning support

---

### 3. Transformation: dbt + Medallion Architecture

#### Bronze Layer: `raw.crypto_prices`

- **Immutable landing zone** - flattened time-series data from CoinGecko API
- **Pre-flattened during ingestion** - nested API response is unnested before storage
- **Partitioned by coin** - each cryptocurrency is a separate Dagster partition
- **Incremental loading** - fetches only new data since last timestamp
- **Hourly resampling** - normalizes all data to consistent hourly granularity

**Data Structure (Pre-flattened):**

```text
┌─────────────────────────────────────────────────────────────┐
│ coin: "bitcoin"                                             │
│ currency: "usd"                                             │
│ ingested_at: 2026-03-01T10:30:00                           │
│ recorded_at: 2026-03-01T10:00:00                           │
│ price: 42500.00                                            │
│ market_cap: 850000000000.00                                │
│ volume: 25000000000.00                                     │
└─────────────────────────────────────────────────────────────┘
```

**Note:** The nested API response (`prices: [[timestamp_ms, price], ...]`) is flattened during ingestion by the `unnest_market_data()` function before being written to DuckDB.

**Schema Validation:**

```python
class EnhancedMarketSchema(pa.DataFrameModel):
    """Enhanced schema with business logic constraints."""
    coin: str = pa.Field(nullable=False)
    currency: str = pa.Field(nullable=False)
    ingested_at: pendulum.DateTime = pa.Field(nullable=False)
    recorded_at: pendulum.DateTime = pa.Field(nullable=False)
    price: float = pa.Field(gt=0, nullable=False)  # Must be positive
    market_cap: float = pa.Field(gt=0, nullable=False)
    volume: float = pa.Field(gt=0, nullable=False)
```

#### Silver Layer: `staging.stg_crypto_prices`

- **Clean and validate** pre-flattened data from Bronze layer
- **Type casting and rounding** for precision
- **Incremental processing** with watermark per coin
- **Deduplication** with deterministic selection (latest ingested_at wins)

```sql
{{ config(
    materialized='incremental',
    unique_key=['coin', 'recorded_at'],
    on_schema_change='sync_all_columns',
    cluster_by=['coin', 'recorded_at']
) }}

with raw_data as (
    select
        coin, currency, ingested_at, recorded_at, price, market_cap, volume
    from {{ source('coingecko', 'crypto_prices') }}
),

filtered as (
    select
        coin,
        currency,
        ingested_at,
        recorded_at,
        round(price, 8) as price,
        round(market_cap, 2) as market_cap,
        round(volume, 2) as volume
    from raw_data
    where
        price > 0
        and recorded_at is not null
        and market_cap >= 0
        and volume >= 0
)

-- Incremental processing with watermark
-- Deduplication with deterministic selection
select distinct on (coin, recorded_at)
    coin, currency, ingested_at, recorded_at, price, market_cap, volume
from filtered
order by coin asc, recorded_at asc, ingested_at desc
```

#### Gold Layer: `mart.fct_crypto_candlesticks` (Table)

- **Business-ready OHLC metrics** with moving averages
- **Daily aggregations** per cryptocurrency
- **Table materialization** for correct window function calculations
- **Reusable macros** for financial calculations

```sql
with ohlc_base as (
    select
        coin,
        date_trunc('day', recorded_at)::date as trade_date,
        arg_min(price, recorded_at) as open_price,
        max(price) as high_price,
        min(price) as low_price,
        arg_max(price, recorded_at) as close_price,
        sum(volume) as daily_volume,
        count(*) as samples_count,
        {{ calculate_volatility('max(price)', 'min(price)') }} as volatility_pct
    from {{ ref('stg_crypto_prices') }}
    group by coin, date_trunc('day', recorded_at)::date
),

with_smas as (
    select
        *,
        {{ calculate_simple_moving_average('close_price', 7) }} as sma_7,
        {{ calculate_simple_moving_average('close_price', 25) }} as sma_25,
        {{ calculate_price_change('open_price', 'close_price') }} as daily_change_pct,
        {{ calculate_price_range('high_price', 'low_price') }} as price_range
    from ohlc_base
)

select * from with_smas order by coin, trade_date
```

**Materialization strategy:**

- Table materialization for correct SMA calculations
- DuckDB efficiently handles full recomputation
- Window functions require full historical context
- Strategic indexes on `(coin, trade_date)`, `trade_date`, and `coin`

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
def crypto_prices() -> pl.DataFrame:
    return pl.DataFrame(...)  # Automatically saved to DuckDB
```

---

### 5. Visualization: Streamlit

**Purpose**: Interactive dashboard querying Gold layer

```python
conn = duckdb.connect('data/crypto.duckdb')
df = conn.execute("SELECT * FROM mart.fct_crypto_candlesticks").pl()

fig = go.Figure(data=[go.Candlestick(
    x=df['trade_date'],
    open=df['open_price'],
    high=df['high_price'],
    low=df['low_price'],
    close=df['close_price']
)])
```

**Features:**

- Multi-cryptocurrency selection
- Real-time price tracking
- Interactive OHLC charts
- Volume analysis
- Volatility metrics

---

## 🔄 Data Flow

1. **Trigger**: User runs `make pipeline` or Dagster materializes assets
2. **Extract**: PyAirbyte fetches CoinGecko data for each partition (coin)
3. **Load**: Raw nested data lands in `raw.crypto_prices` (Bronze)
4. **Transform Silver**: dbt unnests and cleans data → `staging.stg_crypto_prices`
5. **Transform Gold**: dbt aggregates to OHLC → `mart.fct_crypto_candlesticks`
6. **Visualize**: Streamlit queries Gold layer → renders multi-coin dashboard

---

## 🎯 Technology Choices

### PyAirbyte vs. Custom API Code

✅ **PyAirbyte**: Battle-tested, error handling, schema validation
❌ Custom code: Need to implement retries, validation, rate limiting

### Dagster vs. Airflow

✅ **Dagster**: Asset-centric, auto lineage, native Python, partitioning
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

| Scenario       | Full Refresh | Incremental  |
| -------------- | ------------ | ------------ |
| 1 year data    | 60 seconds   | 0.5 seconds  |
| 5 years data   | 5 minutes    | 0.5 seconds  |

### 2. Polars Over Pandas

**Impact**: 5-10x faster DataFrame operations

| Operation        | Pandas | Polars |
| ---------------- | ------ | ------ |
| CSV read (1GB)   | 12s    | 2s     |
| GroupBy          | 8s     | 0.8s   |
| Join (1M rows)   | 5s     | 0.5s   |

### 3. Enhanced Performance Results

**Pipeline Execution Times:**

- Parse: 0.58s
- Compile: 0.46s
- Tests: 0.64s (46 tests)
- Build: 1.06s (48 operations)
- Documentation: Generated successfully

**Database Performance:**

- 10 cryptocurrencies, multiple years of data
- All tests passing with 100% success rate
- SQLFluff compliant with 0 warnings
- **91 total tests** covering data quality, transformations, and integration
- **Enhanced data quality gates** with comprehensive validation

### 3. DuckDB Columnar Storage

- Only reads needed columns
- Vectorized execution (SIMD)
- Parallel query execution

### 4. Dagster Partitioning

- Process multiple coins in parallel
- Isolated execution per partition
- Independent retry policies

### 5. Enhanced Performance & Quality Features

**Impact**: Improved reliability, maintainability, and data quality

- **Rate limiting with exponential backoff**: Prevents API throttling and improves reliability
- **Memory-efficient data processing**: Optimized DataFrame operations and connection pooling
- **Smart refresh logic**: Always re-processes current day for intra-day accuracy
- **Comprehensive test coverage**: 91 tests covering data quality, transformations, and integration
- **Strict type checking**: pyright integration with CI for better code quality
- **Enhanced error handling**: Better logging and user feedback throughout the pipeline
- **Code quality automation**: Pre-commit hooks with Ruff, SQLFluff, and pyright
- **Data quality gates**: Multi-layered validation from ingestion to Gold layer

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
│   └── crypto_prices          # Nested raw data, partitioned by coin
├── staging (Silver)
│   └── stg_crypto_prices      # Flattened, cleaned time-series
└── mart (Gold)
    └── fct_crypto_candlesticks # Daily OHLC per cryptocurrency
```

---

## 📚 Related Documentation

- [Data Modeling](data-modeling.md) - Deep dive into Medallion layers
- [Setup Guide](setup-guide.md) - Installation and configuration
- [Testing Guide](testing.md) - Testing strategy and writing tests

---

**[← Back to Documentation Index](index.md)**
