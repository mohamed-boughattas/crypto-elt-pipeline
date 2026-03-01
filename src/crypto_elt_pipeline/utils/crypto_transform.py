"""Data transformation utilities for cryptocurrency market data.

This module provides functions for transforming raw API responses into
usable time-series data, including validation, unnesting, and resampling.
"""

import numpy as np
import pandera.polars as pa
import pendulum
import polars as pl


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
    Matches validation rules in dbt staging layer (stg_crypto_prices.sql).
    """

    coin: str = pa.Field(nullable=False)
    currency: str = pa.Field(nullable=False)
    ingested_at: pl.Datetime = pa.Field(nullable=False)
    recorded_at: pl.Datetime = pa.Field(nullable=False)
    price: float = pa.Field(gt=0, nullable=False)  # Business rule: Prices must be positive
    market_cap: float = pa.Field(
        ge=0, nullable=False
    )  # Business rule: Market cap must be non-negative (matches dbt)
    volume: float = pa.Field(
        ge=0, nullable=False
    )  # Business rule: Volume must be non-negative (matches dbt)

    class Config:
        strict = False  # Allow additional columns
        coerce = True  # Automatically coerce types when possible


def validate_raw_data(raw_df: pl.DataFrame) -> None:
    """Validate raw API response structure.

    Args:
        raw_df: Raw DataFrame with nested lists

    Raises:
        pandera.errors.SchemaError: If validation fails
        ValueError: If raw data is invalid or malformed
        RuntimeError: If validation fails unexpectedly
    """
    try:
        if raw_df.is_empty():
            raise ValueError("Raw data is empty - no API response received")

        RawMarketChartSchema.validate(raw_df)
    except pa.errors.SchemaError as e:
        raise ValueError(f"Raw data validation failed: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error during raw data validation: {str(e)}") from e


def validate_enhanced_data(df: pl.DataFrame) -> None:
    """Validate flattened data with business logic constraints.

    Args:
        df: Flattened DataFrame with market data

    Raises:
        pandera.errors.SchemaError: If validation fails
    """
    EnhancedMarketSchema.validate(df)


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

    Raises:
        ValueError: If raw data structure is invalid
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
    # Guard against unexpected multi-row response from API
    if raw_df.height != 1:
        raise ValueError(
            f"Expected exactly 1 row from API, got {raw_df.height}. "
            "API response format may have changed."
        )

    prices_data = raw_df["prices"].item()
    market_caps_data = raw_df["market_caps"].item()
    volumes_data = raw_df["total_volumes"].item()

    # Validate that all lists have the same length
    n_records = len(prices_data)
    if len(market_caps_data) != n_records or len(volumes_data) != n_records:
        raise ValueError(
            f"Data length mismatch: prices={len(prices_data)}, "
            f"market_caps={len(market_caps_data)}, volumes={len(volumes_data)}"
        )

    # Convert to numpy arrays for faster processing
    # Convert Polars Series to list first before numpy conversion
    prices_array = np.array(list(prices_data), dtype=np.float64)
    market_caps_array = np.array(list(market_caps_data), dtype=np.float64)
    volumes_array = np.array(list(volumes_data), dtype=np.float64)

    # Extract columns efficiently
    timestamps = prices_array[:, 0]
    prices = prices_array[:, 1]
    market_caps = market_caps_array[:, 1]
    volumes = volumes_array[:, 1]

    # Create DataFrame efficiently with numpy arrays
    flattened_df = pl.DataFrame(
        {
            "timestamp_ms": timestamps,
            "price": prices,
            "market_cap": market_caps,
            "volume": volumes,
        }
    )

    # Convert timestamp from milliseconds to datetime and add metadata
    current_time = pendulum.now("UTC")
    flattened_df = flattened_df.with_columns(
        [
            pl.from_epoch("timestamp_ms", time_unit="ms")
            .cast(pl.Datetime("us"))
            .alias("recorded_at"),
            pl.lit(coin_id).cast(pl.String).alias("coin"),
            pl.lit(vs_currency).cast(pl.String).alias("currency"),
            pl.lit(current_time).alias("ingested_at"),
        ]
    ).drop("timestamp_ms")

    # Reorder columns efficiently
    return flattened_df.select(
        ["coin", "currency", "ingested_at", "recorded_at", "price", "market_cap", "volume"]
    )


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


def merge_data(existing_df: pl.DataFrame, new_df: pl.DataFrame) -> pl.DataFrame:
    """Merge new data with existing data, deduplicating by recorded_at.

    Timezone Handling:
        - Converts all timestamps to timezone-naive (removes tz info)
        - Assumption: All timestamps are in UTC before conversion
        - This ensures consistency across different data sources/versions
        - DuckDB stores timestamps as naive by default

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

    # Ensure consistent datetime types by converting both to timezone-naive
    # This prevents issues when merging data from different sources or versions
    existing_df = existing_df.with_columns(
        pl.col("recorded_at").dt.replace_time_zone(None).alias("recorded_at"),
        pl.col("ingested_at").dt.replace_time_zone(None).alias("ingested_at"),
    )
    new_df = new_df.with_columns(
        pl.col("recorded_at").dt.replace_time_zone(None).alias("recorded_at"),
        pl.col("ingested_at").dt.replace_time_zone(None).alias("ingested_at"),
    )

    # Concatenate and deduplicate by recorded_at (keep last = new data)
    # Sort by ingested_at first to ensure deterministic behavior
    merged = (
        pl.concat([existing_df, new_df])
        .sort("ingested_at")
        .unique(
            subset=["coin", "recorded_at"],
            keep="last",
        )
    )

    return merged.sort("recorded_at")
