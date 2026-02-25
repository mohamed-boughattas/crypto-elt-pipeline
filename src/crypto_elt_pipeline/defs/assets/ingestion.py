"""Ingestion assets for extracting raw cryptocurrency data from CoinGecko.

This module implements the Bronze layer of the ELT pipeline:
- Extracts raw nested market data from CoinGecko API via PyAirbyte
- Unnests the nested lists into flat time-series records
- Stores flattened data in DuckDB via IO manager
- Supports incremental loading to fetch only new data

Architecture:
    CoinGecko API → PyAirbyte → raw_crypto_prices (Bronze) → dbt staging (Silver)
"""

import os
import random
import time
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

import airbyte as ab
import dagster as dg
import duckdb
import pandera.polars as pa
import pendulum
import polars as pl

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.constants import DUCKDB_PATH

# Optional CoinGecko API key for Pro API access (higher rate limits)
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY")

# ------------------------------------------------------------------
# Data Contracts (Pandera) - Enhanced with Business Logic
# ------------------------------------------------------------------


class RawMarketChartSchema(pa.DataFrameModel):
    """Validates the raw nested structure from CoinGecko API.

    The API returns nested lists where each element is [timestamp, value].
    This schema validates the structure before landing in Bronze.
    """

    prices: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})
    market_caps: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})
    total_volumes: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})

    class Config:
        strict = False  # Allow additional columns


class EnhancedMarketSchema(pa.DataFrameModel):
    """Enhanced schema with business logic constraints for crypto market data.

    Validates both structure and business rules for cryptocurrency pricing data.
    """

    coin: str = pa.Field(nullable=False)
    currency: str = pa.Field(nullable=False)
    ingested_at: pendulum.DateTime = pa.Field(nullable=False)
    recorded_at: pendulum.DateTime = pa.Field(nullable=False)
    price: float = pa.Field(gt=0, nullable=False)  # Business rule: Prices must be positive
    market_cap: float = pa.Field(gt=0, nullable=False)  # Business rule: Market cap must be positive
    volume: float = pa.Field(gt=0, nullable=False)  # Business rule: Volume must be positive

    class Config:
        strict = False  # Allow additional columns
        coerce = True  # Automatically coerce types when possible


# ------------------------------------------------------------------
# Configuration & Partitions (from centralized config)
# ------------------------------------------------------------------


def _get_crypto_partitions() -> dg.StaticPartitionsDefinition:
    """Get partitions definition from centralized config.

    Uses lazy loading to avoid loading config during module import.
    """
    config = get_config()
    return dg.StaticPartitionsDefinition(config.coin_ids)


# Lazy partition definition
CRYPTO_PARTITIONS = _get_crypto_partitions()


# ------------------------------------------------------------------
# Incremental Loading Helpers
# ------------------------------------------------------------------


def get_latest_timestamp(coin_id: str) -> pendulum.DateTime | None:
    """Get the latest recorded_at timestamp for a coin from DuckDB.

    Args:
        coin_id: Cryptocurrency identifier

    Returns:
        Latest timestamp as timezone-aware UTC datetime, or None if no data exists
    """
    try:
        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
            result = conn.execute(
                "SELECT MAX(recorded_at) FROM raw.crypto_prices WHERE coin = ?",
                [coin_id],
            ).fetchone()
            if result and result[0]:
                # Convert to timezone-aware UTC datetime
                ts = result[0]
                if ts.tzinfo is None:
                    # Assume UTC if no timezone info
                    return pendulum.instance(ts, tz="UTC")
                return pendulum.instance(ts)
            return None
    except (duckdb.Error, FileNotFoundError):
        # Table doesn't exist yet or database doesn't exist
        return None


def calculate_days_to_fetch(latest_timestamp: pendulum.DateTime | None, default_days: int) -> int:
    """Calculate how many days of data to fetch based on latest timestamp.

    Args:
        latest_timestamp: Latest timestamp in existing data, or None
        default_days: Default number of days to fetch if no data exists

    Returns:
        Number of days to fetch (minimum 1, maximum default_days)
    """
    if latest_timestamp is None:
        return default_days

    # Calculate days since last record
    now = pendulum.now("UTC")
    days_diff = (now - latest_timestamp).days

    # Fetch at least 1 day (to get today's data) and at most default_days
    return max(1, min(days_diff + 1, default_days))


def get_existing_data(coin_id: str) -> pl.DataFrame:
    """Get existing data for a coin from DuckDB.

    Args:
        coin_id: Cryptocurrency identifier

    Returns:
        Polars DataFrame with existing data, or empty DataFrame with schema
    """
    schema = {
        "coin": pl.String,
        "currency": pl.String,
        "ingested_at": pl.Datetime,
        "recorded_at": pl.Datetime,
        "price": pl.Float64,
        "market_cap": pl.Float64,
        "volume": pl.Float64,
    }

    try:
        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
            result = conn.execute(
                "SELECT coin, currency, ingested_at, recorded_at, price, market_cap, volume "
                "FROM raw.crypto_prices WHERE coin = ?",
                [coin_id],
            ).fetchall()
            if result:
                return pl.DataFrame(result, schema=schema, orient="row")
    except (duckdb.Error, FileNotFoundError):
        pass

    return pl.DataFrame(schema=schema)


def merge_data(existing_df: pl.DataFrame, new_df: pl.DataFrame) -> pl.DataFrame:
    """Merge new data with existing data, deduplicating by recorded_at.

    Args:
        existing_df: Existing data
        new_df: New data to merge

    Returns:
        Merged DataFrame with duplicates removed (new data takes precedence)
    """
    if existing_df.is_empty():
        return new_df

    if new_df.is_empty():
        return existing_df

    # Ensure consistent datetime types by converting both to timezone-naive UTC
    existing_df = existing_df.with_columns(
        pl.col("recorded_at").dt.replace_time_zone(None).alias("recorded_at"),
        pl.col("ingested_at").dt.replace_time_zone(None).alias("ingested_at"),
    )
    new_df = new_df.with_columns(
        pl.col("recorded_at").dt.replace_time_zone(None).alias("recorded_at"),
        pl.col("ingested_at").dt.replace_time_zone(None).alias("ingested_at"),
    )

    # Concatenate and deduplicate by recorded_at (keep last = new data)
    merged = pl.concat([existing_df, new_df]).unique(
        subset=["coin", "recorded_at"],
        keep="last",
    )

    return merged.sort("recorded_at")


def resample_to_hourly(df: pl.DataFrame) -> pl.DataFrame:
    """Resample data to hourly granularity.

    CoinGecko API returns different granularity based on days parameter:
    - 1 day: 5-minute intervals
    - 2-90 days: hourly intervals
    - >90 days: daily intervals

    This function normalizes all data to hourly intervals for consistency.

    Args:
        df: DataFrame with potentially mixed granularity

    Returns:
        DataFrame resampled to hourly intervals
    """
    if df.is_empty():
        return df

    # Truncate recorded_at to the hour
    df = df.with_columns(pl.col("recorded_at").dt.truncate("1h").alias("hour"))

    # Aggregate to hourly: take the last value in each hour
    # This preserves the coin, currency columns and aggregates price/market_cap/volume
    hourly_df = df.group_by(["coin", "currency", "hour"]).agg(
        [
            pl.col("ingested_at").last().alias("ingested_at"),
            pl.col("price").last().alias("price"),
            pl.col("market_cap").last().alias("market_cap"),
            pl.col("volume").last().alias("volume"),
        ]
    )

    # Rename hour back to recorded_at and sort
    hourly_df = hourly_df.rename({"hour": "recorded_at"}).sort("recorded_at")

    return hourly_df.select(
        ["coin", "currency", "ingested_at", "recorded_at", "price", "market_cap", "volume"]
    )


class IngestionConfig(dg.Config):
    """Configuration for the CoinGecko ingestion asset.

    Attributes:
        vs_currency: Target currency for price conversion (default: from config)
        days_to_fetch: Number of days of historical data to fetch (default: from config)
    """

    vs_currency: str | None = None
    days_to_fetch: int | None = None

    def get_vs_currency(self) -> str:
        """Get vs_currency from config if not specified."""
        if self.vs_currency is not None:
            return self.vs_currency
        return get_config().ingestion.vs_currency

    def get_days_to_fetch(self) -> int:
        """Get days_to_fetch from config if not specified."""
        if self.days_to_fetch is not None:
            return self.days_to_fetch
        return get_config().ingestion.days_to_fetch


# ------------------------------------------------------------------
# API Rate Limiting & Retry Logic
# ------------------------------------------------------------------


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""

    pass


# ------------------------------------------------------------------
# Ingestion Logic
# ------------------------------------------------------------------


def fetch_coingecko_data(
    coin_id: str,
    vs_currency: str,
    days: int,
    context: dg.AssetExecutionContext,
) -> pl.DataFrame:
    """Fetch raw market data from CoinGecko API via PyAirbyte.

    Implements exponential backoff retry for API failures and rate limits.

    Args:
        coin_id: Cryptocurrency identifier (e.g., 'bitcoin', 'ethereum')
        vs_currency: Target currency for price conversion
        days: Number of days of historical data
        context: Dagster asset execution context for logging

    Returns:
        Polars DataFrame with raw nested API response

    Raises:
        ValueError: If no records are returned from the API
        RateLimitError: If API rate limit is exceeded
    """
    config = get_config()

    # Calculate date range excluding today (only complete days)
    # This ensures consistent record counts across all coins
    yesterday = pendulum.now("UTC").subtract(days=1)
    start_date = yesterday.subtract(days=days - 1).strftime("%d-%m-%Y")
    end_date = yesterday.strftime("%d-%m-%Y")

    # Validate days is one of the allowed values for CoinGecko connector
    allowed_days = ["1", "7", "14", "30", "90", "180", "365", "max"]
    days_str = str(days)
    if days_str not in allowed_days:
        # Round up to nearest allowed value
        days_int = int(days)
        for allowed in ["1", "7", "14", "30", "90", "180", "365", "max"]:
            if allowed == "max" or int(allowed) >= days_int:
                days_str = allowed
                break

    context.log.info(f"Fetching {coin_id} data (Last {days_str} complete days)...")
    context.log.debug(f"Date range: {start_date} to {end_date} (excluding today)")

    # Log API key status
    if COINGECKO_API_KEY:
        context.log.debug("Using CoinGecko Pro API key for higher rate limits")

    def _fetch_with_retry() -> pl.DataFrame:
        """Fetch data with exponential backoff and jitter for rate limits."""
        # Use config values for retry settings
        max_retries = config.ingestion.retry_max_attempts
        base_delay = config.ingestion.retry_base_delay
        max_delay = config.ingestion.retry_max_delay

        for attempt in range(max_retries + 1):
            start_time = time.time()

            try:
                # Build source config with optional API key
                source_config = {
                    "coin_id": coin_id,
                    "vs_currency": vs_currency,
                    "days": days_str,
                    "start_date": start_date,
                    "end_date": end_date,
                }

                # Redirect stdout/stderr to suppress low-level connector noise
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    source = ab.get_source(
                        config.api.connector,
                        docker_image="airbyte/source-coingecko-coins:0.2.26",
                        config=source_config,
                        install_if_missing=True,
                    )
                    source.check()
                    source.select_streams(["market_chart"])
                    records = list(source.get_records("market_chart"))

                if not records:
                    raise ValueError(f"No records found for {coin_id}")

                execution_time = time.time() - start_time
                records_count = len(records)

                context.log.info(
                    f"✅ Successfully fetched {records_count} records in {execution_time:.2f}s"
                )

                return pl.DataFrame([dict(r) for r in records], strict=False)

            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e).lower()

                # Check for rate limit specific errors
                if any(
                    rate_limit_indicator in error_msg
                    for rate_limit_indicator in [
                        "rate limit",
                        "429",
                        "too many requests",
                        "limit exceeded",
                        "request limit",
                        "api limit",
                        "quota",
                        "throttled",
                    ]
                ):
                    if attempt < max_retries:
                        # Exponential backoff with jitter to avoid thundering herd
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = delay * (0.5 + random.random())  # Add 50-150% jitter
                        context.log.warning(
                            f"⚠️ Rate limit hit for {coin_id} (attempt {attempt + 1}/{max_retries}). "
                            f"Waiting {jitter:.1f}s before retry..."
                        )
                        time.sleep(jitter)
                        continue
                    else:
                        # Final attempt failed due to rate limit
                        raise RateLimitError(
                            f"Rate limit exceeded for {coin_id} after {max_retries} retries. "
                            f"Please try again later or reduce the frequency of requests."
                        ) from e

                # For non-rate-limit errors, log and re-raise immediately
                context.log.error(f"❌ Failed to fetch data after {execution_time:.2f}s: {e}")
                raise

    # Execute fetch with retry logic
    return _fetch_with_retry()


def unnest_market_data(raw_df: pl.DataFrame, coin_id: str, vs_currency: str) -> pl.DataFrame:
    """Unnest the nested list structure into flat time-series records.

    The CoinGecko API returns data as nested lists:
        prices: [[timestamp_ms, price], ...]
        market_caps: [[timestamp_ms, market_cap], ...]
        total_volumes: [[timestamp_ms, volume], ...]

    This function flattens them into a single DataFrame with one row per timestamp.

    Args:
        raw_df: Raw DataFrame with nested lists
        coin_id: Cryptocurrency identifier
        vs_currency: Target currency

    Returns:
        Flattened DataFrame with one row per timestamp
    """
    if raw_df.is_empty():
        return pl.DataFrame(
            schema={
                "coin": pl.String,
                "currency": pl.String,
                "ingested_at": pl.Datetime,
                "recorded_at": pl.Datetime,
                "price": pl.Float64,
                "market_cap": pl.Float64,
                "volume": pl.Float64,
            }
        )

    # Extract the nested lists from the first row (all data is in one row from API)
    prices_data = raw_df["prices"].item()
    market_caps_data = raw_df["market_caps"].item()
    volumes_data = raw_df["total_volumes"].item()

    # Create separate DataFrames for each metric
    prices_df = pl.DataFrame(
        {
            "timestamp_ms": [p[0] for p in prices_data],
            "price": [p[1] for p in prices_data],
        }
    )

    market_caps_df = pl.DataFrame(
        {
            "timestamp_ms": [m[0] for m in market_caps_data],
            "market_cap": [m[1] for m in market_caps_data],
        }
    )

    volumes_df = pl.DataFrame(
        {
            "timestamp_ms": [v[0] for v in volumes_data],
            "volume": [v[1] for v in volumes_data],
        }
    )

    # Join all metrics on timestamp
    flattened_df = prices_df.join(market_caps_df, on="timestamp_ms", how="inner")
    flattened_df = flattened_df.join(volumes_df, on="timestamp_ms", how="inner")

    # Convert timestamp from milliseconds to datetime
    # Polars Datetime expects microseconds by default, so multiply ms by 1000 to get us
    flattened_df = flattened_df.with_columns(
        [
            (pl.col("timestamp_ms") * 1000).cast(pl.Datetime("us")).alias("recorded_at"),
        ]
    ).drop("timestamp_ms")

    # Add metadata columns
    flattened_df = flattened_df.with_columns(
        [
            pl.lit(coin_id).cast(pl.String).alias("coin"),
            pl.lit(vs_currency).cast(pl.String).alias("currency"),
            pl.lit(pendulum.now("UTC")).alias("ingested_at"),
        ]
    )

    # Reorder columns
    return flattened_df.select(
        ["coin", "currency", "ingested_at", "recorded_at", "price", "market_cap", "volume"]
    )


# ------------------------------------------------------------------
# Asset Definition - Bronze Layer (Raw)
# ------------------------------------------------------------------


@dg.asset(
    deps=["coingecko_api"],
    group_name="Bronze",
    kinds={"airbyte", "duckdb"},
    io_manager_key="io_manager",
    key_prefix=["raw"],
    partitions_def=CRYPTO_PARTITIONS,
    retry_policy=dg.RetryPolicy(
        max_retries=2,  # 2 retries on failure
        delay=30,  # Wait 30 seconds before retrying
    ),
    metadata={
        "source": "CoinGecko API",
        "connector": "PyAirbyte (source-coingecko-coins)",
        "dagster/storage_kind": "duckdb",
        "partition_expr": "coin",  # Column to partition on for DuckDB IO manager
        "api_docs": dg.MetadataValue.url(
            "https://docs.airbyte.com/integrations/sources/coingecko-coins"
        ),
    },
    tags={
        "layer": "raw",
        "domain": "cryptocurrency",
    },
)
def crypto_prices(context: dg.AssetExecutionContext, config: IngestionConfig) -> pl.DataFrame:
    """Ingests cryptocurrency market data from CoinGecko API.

    This Bronze layer asset extracts data from CoinGecko and flattens
    the nested API response into a time-series format suitable for
    storage in DuckDB via the IO manager.

    Supports incremental loading: fetches only new data since the last
    recorded timestamp, merging with existing data to avoid duplicates.

    The flattening is done here (not in dbt) because:
    1. DuckDB IO manager doesn't handle nested list types well
    2. The data is still "raw" - no business logic transformations
    3. dbt Silver layer will handle cleaning and type enforcement

    Output Columns:
        coin: Cryptocurrency identifier (partition key)
        currency: Target currency (e.g., 'usd')
        ingested_at: Timestamp of data ingestion
        recorded_at: Timestamp of the price observation
        price: Price in the target currency
        market_cap: Market capitalization
        volume: Trading volume

    Args:
        context: Dagster asset execution context
        config: Ingestion configuration (currency, days to fetch)

    Returns:
        Polars DataFrame with flattened time-series data
    """
    coin_id = context.partition_key

    # Defense-in-depth: Validate partition key
    valid_coins = CRYPTO_PARTITIONS.get_partition_keys()
    if coin_id not in valid_coins:
        raise ValueError(f"Invalid partition key: {coin_id}. Expected one of {valid_coins}")

    vs_currency = config.get_vs_currency()
    default_days = config.get_days_to_fetch()

    # 1. Incremental Loading: Check for existing data
    latest_timestamp = get_latest_timestamp(coin_id)
    existing_df = None

    if latest_timestamp is not None:
        days_to_fetch = calculate_days_to_fetch(latest_timestamp, default_days)
        context.log.info(
            f"📅 Existing data found for {coin_id}. "
            f"Latest: {latest_timestamp}. Fetching {days_to_fetch} day(s) of new data."
        )
        existing_df = get_existing_data(coin_id)
    else:
        days_to_fetch = default_days
        context.log.info(f"🆕 No existing data for {coin_id}. Fetching {days_to_fetch} days.")

    # 2. Extraction: Fetch raw nested data via PyAirbyte
    raw_df = fetch_coingecko_data(coin_id, vs_currency, days_to_fetch, context)

    # 3. Raw Validation: Verify API response structure
    try:
        RawMarketChartSchema.validate(raw_df)
        context.log.info(f"✅ Raw schema validation passed for {coin_id}")
    except pa.errors.SchemaError as e:
        context.log.error(f"❌ Raw schema validation failed for {coin_id}: {e}")
        raise

    # 4. Unnest: Flatten nested lists into time-series records
    new_df = unnest_market_data(raw_df, coin_id, vs_currency)
    context.log.info(f"📊 Unnested {new_df.height} records for {coin_id}")

    # 5. Validate flattened data with enhanced schema
    try:
        EnhancedMarketSchema.validate(new_df)
        context.log.info(f"✅ Enhanced schema validation passed for {coin_id}")
    except pa.errors.SchemaError as e:
        context.log.error(f"❌ Enhanced schema validation failed for {coin_id}: {e}")
        raise

    # 6. Merge: Combine with existing data if available
    if existing_df is not None and not existing_df.is_empty():
        final_df = merge_data(existing_df, new_df)
        context.log.info(
            f"🔗 Merged {existing_df.height} existing + {new_df.height} new = {final_df.height} total records"
        )
    else:
        final_df = new_df

    # 7. Resample: Normalize to hourly granularity for consistency
    records_before_resample = final_df.height
    final_df = resample_to_hourly(final_df)
    context.log.info(
        f"📊 Resampled to hourly: {records_before_resample} → {final_df.height} records"
    )

    # 8. Observability: Attach summary stats to Dagster Asset
    new_records = new_df.height
    total_records = final_df.height
    date_range = f"{final_df['recorded_at'].min()} to {final_df['recorded_at'].max()}"

    preview_info = (
        f"| Column | Value |\n|--------|-------|\n"
        f"| coin | {coin_id} |\n"
        f"| currency | {vs_currency} |\n"
        f"| new_records | {new_records} |\n"
        f"| total_records | {total_records} |\n"
        f"| date_range | {date_range} |\n"
    )

    context.add_output_metadata(
        metadata={
            "coin": coin_id,
            "new_records": new_records,
            "total_records": total_records,
            "data_preview": dg.MetadataValue.md(preview_info),
        }
    )

    return final_df
