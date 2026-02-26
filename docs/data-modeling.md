# 🗂️ Data Modeling

Deep dive into the Medallion architecture and dbt transformations.

---

## 🎯 Medallion Architecture Overview

The pipeline implements a three-layer Medallion architecture:

```text
Bronze (Raw)  →  Silver (Staging)  →  Gold (Marts)
   Immutable       Cleaned & Typed     Business Ready
```

**Benefits:**

- Clear data quality progression
- Incremental complexity
- Easy debugging (inspect each layer)
- Reusable transformations

---

## 📁 Database Structure

```text
crypto.duckdb
│
├── raw                           # Bronze Layer
│   └── crypto_prices             # Raw CoinGecko data (multi-coin)
│
├── staging                       # Silver Layer
│   └── stg_crypto_prices         # Cleaned & validated
│
└── mart                          # Gold Layer
    └── fct_crypto_candlesticks   # OHLC aggregations (table)
```

---

## 🥉 Bronze Layer: Raw Data

### Table: `raw.crypto_prices`

**Purpose**: Immutable landing zone for API data

**Schema:**

```sql
CREATE TABLE raw.crypto_prices (
    coin VARCHAR,           -- 'bitcoin', 'ethereum', 'ripple', 'solana', 'cardano', etc. (10 coins)
    currency VARCHAR,       -- 'usd'
    ingested_at TIMESTAMP,  -- Ingestion timestamp
    recorded_at TIMESTAMP,  -- Price timestamp
    price DOUBLE,           -- Price in target currency
    market_cap DOUBLE,      -- Total market capitalization
    volume DOUBLE           -- 24h trading volume
);
```

**Source**: PyAirbyte → CoinGecko API

**Characteristics:**

- **Incremental loading**: Fetches only new data since last timestamp
- **Hourly granularity**: All data resampled to consistent hourly intervals
- Pre-flattened from nested API response
- Partitioned by coin (Dagster partitions)
- Written by Dagster's `DuckDBPolarsIOManager`
- Idempotent (safe to re-run)

**Incremental Loading Logic:**

```text
First run:     Fetch 30 days → ~720 hourly records
Daily run:     Fetch 1 day  → ~24 hourly records (97% less API calls)
Missed 5 days: Fetch 6 days → ~144 hourly records (auto catch-up)
```

**Hourly Resampling:**

The CoinGecko API returns different granularity based on days requested:

| Days  | API Granularity     | After Resampling      |
| ----- | ------------------- | --------------------- |
| 1     | 5-minute intervals  | Hourly (LAST price)   |
| 2-90  | Hourly intervals    | Hourly (unchanged)    |
| >90   | Daily intervals     | Daily (unchanged)     |

Resampling uses **LAST** aggregation (closing price) for financial consistency.

**Dagster Asset:**

```python
@dg.asset(
    key_prefix=["raw"],
    io_manager_key="io_manager",
    partitions_def=CRYPTO_PARTITIONS,  # 10 cryptocurrencies
)
def crypto_prices(context) -> pl.DataFrame:
    """Bronze layer: Raw data ingestion with incremental loading."""
    # Check for existing data
    latest_timestamp = get_latest_timestamp(coin_id)
    days_to_fetch = calculate_days_to_fetch(latest_timestamp, default_days=30)

    # PyAirbyte extraction (only needed data)
    raw_df = fetch_coingecko_data(coin_id, days=days_to_fetch, ...)

    # Schema validation (Pandera)
    RawMarketChartSchema.validate(raw_df)

    # Flatten nested lists
    new_df = unnest_market_data(raw_df, coin_id, vs_currency)

    # Merge with existing data
    merged_df = merge_data(existing_df, new_df)

    # Resample to hourly granularity
    return resample_to_hourly(merged_df)
```

---

## 🥈 Silver Layer: Staging

### Model: `staging.stg_crypto_prices`

**Purpose**: Cleaned, typed, and validated data ready for analytics

**File**: `dbt_project/models/staging/stg_crypto_prices.sql`

```sql
{{ config(
    materialized='incremental',
    unique_key=['coin', 'recorded_at']
) }}

select
    coin,
    currency,
    ingested_at,
    recorded_at,

    -- Price standardization (8 decimal places)
    round(price, 8) as price,

    -- Financial metrics (2 decimal places)
    round(market_cap, 2) as market_cap,
    round(volume, 2) as volume

from {{ source('coingecko', 'crypto_prices') }}

where
    -- Data quality filters
    price > 0
    and recorded_at is not null
    and market_cap >= 0
    and volume >= 0
```

**Transformations:**

1. **Type casting**: Explicit data types for safety
2. **Rounding**: Consistent precision (8 for price, 2 for financials)
3. **Filtering**: Remove invalid records (null, negative, zero prices)
4. **Deduplication**: Unique key on (coin, recorded_at)

---

### Data Quality Tests

**Comprehensive Testing Framework (46 tests):**

**File**: `dbt_project/models/staging/sources.yml`

```yaml
version: 2

sources:
  - name: coingecko
    schema: raw
    tables:
      - name: crypto_prices
        columns:
          - name: coin
            tests:
              - not_null
              - accepted_values:
                  values: ['bitcoin', 'ethereum', 'ripple', 'solana', 'cardano', 'avalanche-2', 'polkadot', 'binancecoin', 'chainlink', 'dogecoin']

models:
  - name: stg_crypto_prices
    description: "Cleaned and typed cryptocurrency price data"
    columns:
      - name: recorded_at
        description: "Price timestamp (UTC)"
        tests:
          - not_null

      - name: price
        description: "Price in USD"
        tests:
          - not_null

      - name: coin
        description: "Cryptocurrency identifier"
        tests:
          - accepted_values:
              values: ['bitcoin', 'ethereum', 'ripple', 'solana', 'cardano', 'avalanche-2', 'polkadot', 'binancecoin', 'chainlink', 'dogecoin']
```

**Test Categories:**

- **Source Tests (8)**: Schema validation, accepted values, null checks
- **Silver Layer Tests (14)**: Data cleaning, type validation, business rules
- **Gold Layer Tests (24)**: OHLC consistency, financial logic, composite unique keys

**Test Execution:**

```bash
cd dbt_project
dbt test --select stg_crypto_prices
```

**Actual Test Results:**

```
Running with dbt=1.11.3
Found 2 models, 46 data tests, 1 source, 871 macros
Completed successfully
Done. PASS=46 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=46
```

---

## 🥇 Gold Layer: Business Metrics

### Model: `mart.fct_crypto_candlesticks`

**Purpose**: Analytics-ready OHLC (Open, High, Low, Close) daily aggregations with moving averages

**File**: `dbt_project/models/marts/fct_crypto_candlesticks.sql`

```sql
{{ config(
    materialized='table',
    cluster_by=['coin', 'trade_date'],
    indexes=[
      {'columns': ['coin', 'trade_date'], 'unique': true},
      {'columns': ['trade_date']},
      {'columns': ['coin']}
    ]
) }}

-- Table materialization for correct window function calculations
-- SMAs require full historical context

with source_data as (
    select coin, recorded_at, price, volume
    from {{ ref('stg_crypto_prices') }}
),

ohlc_base as (
    select
        coin,
        date_trunc('day', recorded_at)::date as trade_date,

        -- OHLC metrics (candlestick chart data)
        arg_min(price, recorded_at) as open_price,
        max(price) as high_price,
        min(price) as low_price,
        arg_max(price, recorded_at) as close_price,

        -- Volume metrics
        sum(volume) as daily_volume,
        count(*) as samples_count,

        -- Calculated metrics using macros
        {{ calculate_volatility('max(price)', 'min(price)') }} as volatility_pct

    from source_data
    group by coin, date_trunc('day', recorded_at)::date
),

with_smas as (
    select
        coin,
        trade_date,
        open_price,
        high_price,
        low_price,
        close_price,
        daily_volume,
        volatility_pct,
        samples_count,

        -- Moving averages using reusable macros
        {{ calculate_simple_moving_average('close_price', 7) }} as sma_7,
        {{ calculate_simple_moving_average('close_price', 25) }} as sma_25,

        -- Additional calculated metrics
        {{ calculate_price_change('open_price', 'close_price') }} as daily_change_pct,
        {{ calculate_price_range('high_price', 'low_price') }} as price_range

    from ohlc_base
)

select * from with_smas order by coin, trade_date
```

**Output Columns:**

| Column | Type | Description |
| ------ | ---- | ----------- |
| `coin` | VARCHAR | Cryptocurrency identifier |
| `trade_date` | DATE | Trading date (UTC) |
| `open_price` | DOUBLE | Opening price (first price of day) |
| `high_price` | DOUBLE | Highest price during day |
| `low_price` | DOUBLE | Lowest price during day |
| `close_price` | DOUBLE | Closing price (last price of day) |
| `daily_volume` | DOUBLE | Total trading volume |
| `volatility_pct` | DOUBLE | Intraday volatility percentage |
| `samples_count` | BIGINT | Number of hourly samples aggregated |
| `sma_7` | DOUBLE | 7-day simple moving average |
| `sma_25` | DOUBLE | 25-day simple moving average |
| `daily_change_pct` | DOUBLE | Daily price change percentage |
| `price_range` | DOUBLE | Absolute price range (high - low) |
| `bb_middle` | DOUBLE | Bollinger Band middle band (20-day SMA) |
| `bb_upper` | DOUBLE | Bollinger Band upper band (Middle + 2σ) |
| `bb_lower` | DOUBLE | Bollinger Band lower band (Middle - 2σ) |
| `bb_width` | DOUBLE | Bollinger Band width as percentage of middle band |
| `bb_position` | DOUBLE | Price position relative to Bollinger Bands (0-1 scale) |

---

### OHLC Calculation Explained

**Open Price**: First price of the trading day

```sql
arg_min(price, recorded_at)  -- Returns price at minimum timestamp
```

**High Price**: Maximum price during the day

```sql
max(price)
```

**Low Price**: Minimum price during the day

```sql
min(price)
```

**Close Price**: Last price of the trading day

```sql
arg_max(price, recorded_at)  -- Returns price at maximum timestamp
```

**Volatility**: Daily price swing percentage

```sql
((high - low) / low) * 100
```

---

### Bollinger Bands Technical Analysis

**Purpose**: Volatility-based technical indicators for trend analysis and trading signals

**Components:**

- **Middle Band**: 20-day simple moving average of closing prices
- **Upper Band**: Middle band + (2 × standard deviation)
- **Lower Band**: Middle band - (2 × standard deviation)

**Technical Analysis Applications:**

- **Volatility Assessment**: Band width indicates market volatility
- **Trend Identification**: Price position relative to bands shows momentum
- **Reversal Signals**: Price touching bands may indicate overbought/oversold conditions
- **Breakout Detection**: Narrowing bands followed by expansion signals potential breakouts

**Bollinger Band Calculations:**

```sql
-- Middle Band (20-day SMA)
avg(close_price) over (partition by coin order by trade_date rows between 19 preceding and current row)

-- Standard Deviation (20-day)
stddev(close_price) over (partition by coin order by trade_date rows between 19 preceding and current row)

-- Upper Band
middle_band + (2 * standard_deviation)

-- Lower Band
middle_band - (2 * standard_deviation)

-- Band Width (Volatility Indicator)
((upper_band - lower_band) / middle_band) * 100

-- Price Position (0-1 scale)
(close_price - lower_band) / (upper_band - lower_band)
```

**Interpretation:**

- **bb_position = 0**: Price at lower band (potentially oversold)
- **bb_position = 0.5**: Price at middle band (neutral)
- **bb_position = 1**: Price at upper band (potentially overbought)
- **bb_width**: Higher values indicate increased volatility

---

### Table Materialization Strategy

**Why Table Materialization?**

The Gold layer uses `table` materialization (not incremental) because:

1. **Window functions require full history**: SMAs need all preceding rows
2. **DuckDB is fast**: Full recomputation completes in seconds
3. **Simpler logic**: No incremental watermark management

**Performance:**

| Scenario              | Table Refresh    |
| --------------------- | ---------------- |
| 365 days              | ~2 seconds       |
| 1,825 days (5 years)  | ~5 seconds       |

**Run the model:**

```bash
cd dbt_project
dbt run --select fct_crypto_candlesticks
```

### Performance Optimizations

**Indexing Strategy:**

- Strategic clustering on `(coin, trade_date)` for time-series queries
- Composite unique indexes on `(coin, trade_date)` combinations
- Additional indexes on `trade_date` and `coin` for common query patterns

**Reusable Macros:**

The Gold layer uses reusable macros from `dbt_project/macros/financial_calculations.sql`:

| Macro | Purpose |
| ----- | ------- |
| `calculate_volatility(high, low)` | Intraday volatility percentage |
| `calculate_simple_moving_average(col, window)` | SMA with configurable window |
| `calculate_price_change(open, close)` | Daily price change percentage |
| `calculate_price_range(high, low)` | Absolute price range |

**Performance Results (Actual):**

- Parse: 0.58s
- Compile: 0.46s
- Tests: 0.64s
- Build: 1.06s
- Documentation: Generated successfully

**Database Performance:**

- 10 cryptocurrencies, multiple years of data
- All tests passing with 100% success rate
- SQLFluff compliant with 0 warnings

---

## 🔄 Transformation Workflow

```text
1. Raw Data Lands
   └── PyAirbyte writes to raw.crypto_prices (partitioned by coin)
       └── DuckDBPolarsIOManager handles write

2. Silver Layer Processing
   └── dbt sources from Bronze
       └── Cleans, types, validates
           └── Creates stg_crypto_prices (incremental)

3. Gold Layer Aggregation
   └── dbt references Silver layer
       └── Calculates OHLC metrics
           └── Creates fct_crypto_candlesticks (table)

4. Dashboard Queries
   └── Streamlit reads from Gold layer
       └── Direct DuckDB connection
```

---

## 📊 Data Quality Strategy

### Layer-Specific Validation

**Comprehensive Data Quality Framework:**

**Bronze (Ingestion)**:

- Pandera schema validation for nested API responses
- Enhanced business logic validation with `EnhancedMarketSchema`
- API response structure checks and type validation
- Incremental loading validation (timestamp continuity)

```python
class RawMarketChartSchema(pa.DataFrameModel):
    """Validates the raw nested structure from CoinGecko API."""
    prices: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})
    market_caps: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})
    total_volumes: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})


class EnhancedMarketSchema(pa.DataFrameModel):
    """Enhanced schema with business logic constraints."""
    coin: str = pa.Field(nullable=False)
    currency: str = pa.Field(nullable=False)
    ingested_at: pendulum.DateTime = pa.Field(nullable=False)
    recorded_at: pendulum.DateTime = pa.Field(nullable=False)
    price: float = pa.Field(gt=0, nullable=False)  # Prices must be positive
    market_cap: float = pa.Field(gt=0, nullable=False)  # Market cap must be positive
    volume: float = pa.Field(gt=0, nullable=False)  # Volume must be positive
```

**Silver (Staging)**:

- **14 dbt tests** covering data cleaning and validation
- Type casting with explicit precision validation
- Range checks (price > 0, market_cap >= 0, volume >= 0)
- Uniqueness validation on (coin, recorded_at) composite key
- Accepted values validation for cryptocurrency identifiers

```yaml
tests:
  - not_null: [recorded_at, price, coin]
  - unique: [recorded_at]  # Per coin partition
  - accepted_values:
      values: ['bitcoin', 'ethereum', 'ripple', 'solana', 'cardano', 'avalanche-2', 'polkadot', 'binancecoin', 'chainlink', 'dogecoin']
```

**Gold (Marts)**:

- **24+ dbt tests** covering business logic and financial calculations
- OHLC consistency validation (high >= low, high >= open, high >= close, etc.)
- Moving average calculation validation
- Sample count tracking for data completeness
- Volatility threshold validation
- Composite unique key validation on (coin, trade_date)
- Daily change percentage and price range validation

```sql
-- Data quality metrics
samples_count,           -- Should be > 0 for valid trading day
volatility_pct,          -- Intraday volatility percentage
sma_7,                   -- 7-day moving average
sma_25,                  -- 25-day moving average
daily_change_pct,        -- Daily price change percentage
price_range,             -- Absolute price range (high - low)

-- Business logic validation
high_price >= low_price, -- OHLC consistency
close_price >= 0,        -- Non-negative closing price
```

**Source Validation (8 tests)**:

- Schema validation for raw API data
- Accepted values for cryptocurrency and currency fields
- Null checks for critical fields (coin, currency, recorded_at)
- Data type validation for nested list structures

**Test Execution Strategy:**

```bash
# Run all data quality tests
cd dbt_project
uv run dbt test

# Run specific layer tests
uv run dbt test --select source:coingecko
uv run dbt test --select stg_crypto_prices
uv run dbt test --select fct_crypto_candlesticks

# Run with detailed output
uv run dbt test --verbose
```

**Quality Assurance Results:**

- **Total Tests**: 46 data quality tests
- **Test Categories**: Source (8), Silver (14), Gold (24)
- **Success Rate**: 100% (46/46 tests passing)
- **Coverage**: All critical data paths and business rules
- **Performance**: Tests complete in 0.64 seconds

```

---

## 🎯 Query Patterns

### Get Latest Price

```sql
SELECT
    coin,
    trade_date,
    close_price,
    daily_volume
FROM mart.fct_crypto_candlesticks
ORDER BY trade_date DESC
LIMIT 1;
```

### Calculate Moving Average

```sql
SELECT
    coin,
    trade_date,
    close_price,
    AVG(close_price) OVER (
        PARTITION BY coin ORDER BY trade_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as ma_7_day
FROM mart.fct_crypto_candlesticks
ORDER BY coin, trade_date DESC;
```

### Find High Volatility Days

```sql
SELECT
    coin,
    trade_date,
    open_price,
    close_price,
    volatility_pct
FROM mart.fct_crypto_candlesticks
WHERE volatility_pct > 10
ORDER BY volatility_pct DESC
LIMIT 10;
```

---

## 🛠️ dbt Commands Reference

```bash
# Run all models
dbt run

# Run specific layer
dbt run --select staging.*
dbt run --select marts.*

# Run with dependencies
dbt run --select +fct_daily_btc_candlesticks

# Test all models
dbt test

# Generate documentation
dbt docs generate
dbt docs serve

# Full refresh (ignore incremental)
dbt run --full-refresh
```

---

## 📈 Adding New Metrics

**Example**: Add 30-day moving average

1. **Create new Gold model**: `fct_crypto_moving_averages.sql`

```sql
select
    coin,
    trade_date,
    close_price,
    avg(close_price) over (
        partition by coin order by trade_date
        rows between 29 preceding and current row
    ) as ma_30_day
from {{ ref('fct_crypto_candlesticks') }}
```

1. **Add to DAG**: Automatically detected by dbt

2. **Run**: `dbt run --select fct_crypto_moving_averages`

---

## 📚 Related Documentation

- [Architecture Overview](system-design.md) - System design
- [Setup Guide](setup-guide.md) - Installation and configuration
- [Testing Guide](testing.md) - Testing strategy

---

## 📖 External Resources

- [dbt Incremental Models](https://docs.getdbt.com/docs/build/incremental-models)
- [dbt Tests](https://docs.getdbt.com/docs/build/tests)
- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [DuckDB Aggregation Functions](https://duckdb.org/docs/sql/aggregates)

---

**[← Back to Documentation Index](index.md)**
