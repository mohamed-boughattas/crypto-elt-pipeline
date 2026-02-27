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

import dagster as dg
import polars as pl

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.utils.crypto_api import fetch_coingecko_data
from crypto_elt_pipeline.utils.crypto_db import (
    calculate_days_to_fetch,
    get_existing_data,
    get_latest_timestamp,
)
from crypto_elt_pipeline.utils.crypto_transform import (
    merge_data,
    resample_to_hourly,
    unnest_market_data,
)

# Optional CoinGecko API key for Pro API access (higher rate limits)
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY")

# ------------------------------------------------------------------
# Data Contracts (Pandera) - Enhanced with Business Logic
# ------------------------------------------------------------------


def validate_raw_data(df: pl.DataFrame) -> pl.DataFrame:
    """Validate raw nested data structure from CoinGecko API.

    The API returns nested lists where each element is [timestamp, value].
    This function validates the structure before landing in Bronze.

    Args:
        df: Raw DataFrame with nested lists

    Returns:
        Validated DataFrame

    Raises:
        ValueError: If validation fails
    """
    try:
        # Check required columns exist
        required_columns = ["prices", "market_caps", "total_volumes"]
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Check that we have at least one row
        if df.height == 0:
            raise ValueError("DataFrame cannot be empty")

        # Check that the first row has the expected structure
        # The data might be in different formats, so be more flexible
        first_row = df.row(0)

        # Find the index of each column
        prices_idx = df.columns.index("prices") if "prices" in df.columns else -1
        market_caps_idx = df.columns.index("market_caps") if "market_caps" in df.columns else -1
        total_volumes_idx = (
            df.columns.index("total_volumes") if "total_volumes" in df.columns else -1
        )

        # Check if we have the expected data structure
        if prices_idx >= 0:
            prices_data = first_row[prices_idx]
            if not isinstance(prices_data, list):
                raise ValueError("prices column should contain lists")
            if len(prices_data) == 0:
                raise ValueError("prices list cannot be empty")

        if market_caps_idx >= 0:
            market_caps_data = first_row[market_caps_idx]
            if not isinstance(market_caps_data, list):
                raise ValueError("market_caps column should contain lists")
            if len(market_caps_data) == 0:
                raise ValueError("market_caps list cannot be empty")

        if total_volumes_idx >= 0:
            total_volumes_data = first_row[total_volumes_idx]
            if not isinstance(total_volumes_data, list):
                raise ValueError("total_volumes column should contain lists")
            if len(total_volumes_data) == 0:
                raise ValueError("total_volumes list cannot be empty")

        return df
    except Exception as e:
        raise ValueError(f"Raw data validation failed: {e}") from e


def validate_enhanced_data(df: pl.DataFrame) -> pl.DataFrame:
    """Validate flattened market data with business logic constraints.

    Validates both structure and business rules for cryptocurrency pricing data.

    Args:
        df: Flattened DataFrame with market data

    Returns:
        Validated DataFrame

    Raises:
        ValueError: If validation fails
    """
    try:
        # Check required columns exist
        required_columns = [
            "coin",
            "currency",
            "ingested_at",
            "recorded_at",
            "price",
            "market_cap",
            "volume",
        ]
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Check business rules
        if (df["price"] <= 0).any():
            raise ValueError("Prices must be positive")
        if (df["market_cap"] <= 0).any():
            raise ValueError("Market cap must be positive")
        if (df["volume"] <= 0).any():
            raise ValueError("Volume must be positive")

        # Check data types
        if not df["coin"].dtype == pl.String:
            raise ValueError("coin column must be string")
        if not df["currency"].dtype == pl.String:
            raise ValueError("currency column must be string")
        if df["price"].dtype not in [pl.Float64, pl.Float32]:
            raise ValueError("price column must be float")
        if df["market_cap"].dtype not in [pl.Float64, pl.Float32]:
            raise ValueError("market_cap column must be float")
        if df["volume"].dtype not in [pl.Float64, pl.Float32]:
            raise ValueError("volume column must be float")

        return df
    except Exception as e:
        raise ValueError(f"Enhanced data validation failed: {e}") from e


# ------------------------------------------------------------------
# Configuration & Partitions (from centralized config)
# ------------------------------------------------------------------


def _get_crypto_partitions() -> dg.StaticPartitionsDefinition:
    """Get partitions definition from centralized config.

    Uses lazy loading to avoid loading config during module import.
    """
    config = get_config()
    return dg.StaticPartitionsDefinition(config.coin_ids)


# Partition definition (loaded at module import time)
# Note: If config/coins.yaml is missing, this will fail during import.
CRYPTO_PARTITIONS = _get_crypto_partitions()


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------


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
        context.log.info(f"📊 Incremental loading for {coin_id.upper()}")
        context.log.info(
            f"📅 Existing data found. Latest: {latest_timestamp}. Fetching {days_to_fetch} day(s) of new data."
        )
        existing_df = get_existing_data(coin_id)
    else:
        days_to_fetch = default_days
        context.log.info(f"🆕 Initial load for {coin_id.upper()}")
        context.log.info(f"Fetching {days_to_fetch} days of historical data.")

    # 2. Extraction: Fetch raw nested data via PyAirbyte
    raw_records = fetch_coingecko_data(coin_id, vs_currency, days_to_fetch, context.log)

    # 3. Raw Validation: Verify API response structure
    try:
        # Convert to DataFrame for validation
        raw_df = pl.DataFrame(raw_records, strict=False)
        validate_raw_data(raw_df)
        context.log.info(f"✅ Raw data validation passed for {coin_id}")
    except ValueError as e:
        context.log.error(f"❌ Raw data validation failed for {coin_id}: {e}")
        raise

    # 4. Unnest: Flatten nested lists into time-series records
    new_df = unnest_market_data(raw_df, coin_id, vs_currency)
    context.log.info(f"📊 Unnested {new_df.height} records for {coin_id}")

    # 5. Validate flattened data with enhanced schema
    try:
        validate_enhanced_data(new_df)
        context.log.info(f"✅ Enhanced data validation passed for {coin_id}")
    except ValueError as e:
        context.log.error(f"❌ Enhanced data validation failed for {coin_id}: {e}")
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
    date_range = f"{final_df['recorded_at'].min()!s} to {final_df['recorded_at'].max()!s}"

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
