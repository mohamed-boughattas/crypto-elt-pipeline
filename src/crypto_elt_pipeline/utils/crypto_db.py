"""Database utilities for cryptocurrency data operations.

This module provides functions for interacting with DuckDB to manage
incremental loading, data retrieval, and database operations for the
crypto ELT pipeline.
"""

import duckdb
import pendulum
import polars as pl

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.constants import DUCKDB_PATH


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
        # Calculate the date filter to avoid loading unbounded history
        # Use configurable history_days from config instead of hardcoded 365
        config = get_config()
        cutoff_date = pendulum.now("UTC").subtract(days=config.ingestion.history_days)

        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
            result = conn.execute(
                "SELECT coin, currency, ingested_at, recorded_at, price, market_cap, volume "
                "FROM raw.crypto_prices WHERE coin = ? AND recorded_at >= ?",
                [coin_id, cutoff_date.isoformat()],
            ).fetchall()
            if result:
                return pl.DataFrame(result, schema=schema, orient="row")
    except (duckdb.Error, FileNotFoundError):
        pass

    return pl.DataFrame(schema=schema)


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
