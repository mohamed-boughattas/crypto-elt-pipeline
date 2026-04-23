"""Ingestion assets for extracting raw cryptocurrency data from CoinGecko.

This module implements the Bronze layer of the ELT pipeline:
- Extracts raw nested market data from CoinGecko API via PyAirbyte
- Unnests the nested lists into flat time-series records
- Stores flattened data in DuckDB via IO manager
- Supports incremental loading to fetch only new data

Architecture:
    CoinGecko API → PyAirbyte → raw_crypto_prices (Bronze) → dbt staging (Silver)
"""

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
    validate_enhanced_data,
    validate_raw_data,
)

# Note: CoinGecko API key is loaded from environment variables.
# Dagster automatically loads .env files, or you can set COINGECKO_API_KEY directly.
# See .env.example for configuration.

# ------------------------------------------------------------------
# Configuration & Partitions (from centralized config)
# ------------------------------------------------------------------

CRYPTO_PARTITIONS = dg.StaticPartitionsDefinition(get_config().coin_ids)


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

    # Add visual separator for better log readability
    context.log.info("\n" + "=" * 50)
    context.log.info(f"Processing {coin_id.upper()}")
    context.log.info("=" * 50)

    vs_currency = config.vs_currency or get_config().ingestion.vs_currency
    default_days = config.days_to_fetch or get_config().ingestion.days_to_fetch

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

    try:
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

    except Exception as e:
        context.log.error(f"❌ Error processing {coin_id}: {type(e).__name__}: {e}")
        raise

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


@dg.asset_check(asset=dg.AssetKey(["raw", "crypto_prices"]))
def check_schema_compatibility(context: dg.AssetCheckExecutionContext) -> dg.AssetCheckResult:
    """Verify schema hasn't drifted from expected columns.

    This asset check runs after the crypto_prices asset materialization
    to ensure the schema remains consistent and catch any breaking changes
    from the CoinGecko API.

    Returns:
        AssetCheckResult with pass/fail status and metadata about any issues
    """
    expected_cols = {
        "coin",
        "currency",
        "ingested_at",
        "recorded_at",
        "price",
        "market_cap",
        "volume",
    }

    try:
        # Query actual schema from DuckDB
        from crypto_elt_pipeline.utils.crypto_db import get_connection_with_retry

        with get_connection_with_retry() as conn:
            result = conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'raw' AND table_name = 'crypto_prices'"
            ).fetchall()

        actual_cols = {row[0] for row in result}
        missing = expected_cols - actual_cols
        extra = actual_cols - expected_cols

        if missing or extra:
            metadata = {}
            if missing:
                metadata["missing_columns"] = str(list(missing))
            if extra:
                metadata["extra_columns"] = str(list(extra))

            return dg.AssetCheckResult(
                passed=False,
                metadata=metadata,
                description=f"Schema drift detected: missing={len(missing)}, extra={len(extra)}",
            )
        else:
            return dg.AssetCheckResult(
                passed=True, description="Schema is compatible with expected structure"
            )

    except Exception as e:
        return dg.AssetCheckResult(
            passed=False,
            metadata={"error": str(e)},
            description=f"Failed to check schema: {str(e)}",
        )


@dg.asset_check(asset=dg.AssetKey(["raw", "crypto_prices"]))
def check_no_null_prices(context: dg.AssetCheckExecutionContext) -> dg.AssetCheckResult:
    """Critical check: No null prices in raw data.

    This asset check ensures data quality by verifying that no records
    have null prices, which would break downstream calculations.

    Returns:
        AssetCheckResult with pass/fail status and null count
    """
    try:
        from crypto_elt_pipeline.utils.crypto_db import get_connection_with_retry

        with get_connection_with_retry() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM raw.crypto_prices WHERE price IS NULL"
            ).fetchone()

        null_count = result[0] if result else 0

        return dg.AssetCheckResult(
            passed=null_count == 0,
            metadata={"null_count": null_count},
            description=f"No null prices: {null_count == 0}",
        )

    except Exception as e:
        return dg.AssetCheckResult(
            passed=False,
            metadata={"error": str(e)},
            description=f"Failed to check for null prices: {str(e)}",
        )
