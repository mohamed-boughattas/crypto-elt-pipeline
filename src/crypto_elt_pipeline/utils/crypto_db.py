"""Database utilities for cryptocurrency data operations.

This module provides functions for interacting with DuckDB to manage
incremental loading, data retrieval, and database operations for the
crypto ELT pipeline.
"""

import random
import time

import duckdb
import pendulum
import polars as pl

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.constants import DUCKDB_PATH


def get_connection_with_retry(
    max_retries: int = 3, base_delay: float = 0.5
) -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection with retry logic for handling locked database errors.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        DuckDB connection

    Raises:
        RuntimeError: If connection fails after all retries
    """
    for attempt in range(max_retries):
        try:
            return duckdb.connect(str(DUCKDB_PATH), read_only=True)
        except duckdb.Error as e:
            error_msg = str(e).lower()
            if "locked" in error_msg and attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Database locked for {DUCKDB_PATH}, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"Failed to connect to database after {max_retries} attempts: {str(e)}"
                ) from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error connecting to database: {str(e)}") from e


def get_latest_timestamp(coin_id: str) -> pendulum.DateTime | None:
    """Get the latest recorded_at timestamp for a coin from DuckDB.

    Args:
        coin_id: Cryptocurrency identifier

    Returns:
        Latest timestamp as timezone-aware UTC datetime, or None if no data exists

    Raises:
        RuntimeError: If database query fails unexpectedly
    """
    try:
        if not DUCKDB_PATH.exists():
            return None

        with get_connection_with_retry() as conn:
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
    except duckdb.Error as e:
        # Handle specific database errors gracefully
        error_msg = str(e).lower()
        if (
            "table not found" in error_msg
            or "no such table" in error_msg
            or "database not found" in error_msg
            or "file not found" in error_msg
        ):
            return None
        elif "permission denied" in error_msg or "access denied" in error_msg:
            raise RuntimeError(f"Database access denied for {coin_id}: {str(e)}") from e
        elif "corrupt" in error_msg or "malformed" in error_msg:
            raise RuntimeError(f"Database file appears corrupted for {coin_id}: {str(e)}") from e
        else:
            # Re-raise unexpected database errors
            raise RuntimeError(f"Database query failed for {coin_id}: {str(e)}") from e
    except Exception as e:
        # Handle any other unexpected errors
        raise RuntimeError(f"Unexpected error getting timestamp for {coin_id}: {str(e)}") from e


def get_existing_data(coin_id: str) -> pl.DataFrame:
    """Get existing data for a coin from DuckDB with performance optimizations.

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
        if not DUCKDB_PATH.exists():
            return pl.DataFrame(schema=schema)

        # Calculate the date filter to avoid loading unbounded history
        # Use configurable history_days from config instead of hardcoded 365
        config = get_config()
        cutoff_date = pendulum.now("UTC").subtract(days=config.ingestion.history_days)

        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
            # Performance optimization: Use prepared statement and limit columns
            # DuckDB can optimize better with explicit column selection
            query = """
                SELECT coin, currency, ingested_at, recorded_at, price, market_cap, volume
                FROM raw.crypto_prices
                WHERE coin = ? AND recorded_at >= ?
                ORDER BY recorded_at DESC
            """

            # Use DuckDB's efficient fetchmany for large datasets
            result = conn.execute(query, [coin_id, cutoff_date.isoformat()])

            # Fetch in batches to handle large datasets efficiently
            batch_size = 10000
            all_rows = []

            while True:
                batch = result.fetchmany(batch_size)
                if not batch:
                    break
                all_rows.extend(batch)

            if all_rows:
                return pl.DataFrame(all_rows, schema=schema, orient="row")

    except duckdb.Error as e:
        error_msg = str(e).lower()
        if "table not found" in error_msg or "no such table" in error_msg:
            return pl.DataFrame(schema=schema)
        else:
            raise RuntimeError(f"Database query failed for {coin_id}: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error getting existing data for {coin_id}: {str(e)}") from e

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


def create_performance_indexes() -> None:
    """Create database indexes for optimal query performance.

    Creates indexes on commonly queried columns to improve:
    - Coin lookups (WHERE coin = ?)
    - Time range queries (WHERE recorded_at >= ?)
    - Combined coin + time queries (WHERE coin = ? AND recorded_at >= ?)
    - Sorting by timestamp (ORDER BY recorded_at)

    This function is idempotent - it can be called multiple times safely.
    """
    try:
        if not DUCKDB_PATH.exists():
            return

        with duckdb.connect(str(DUCKDB_PATH)) as conn:
            # Create indexes if they don't already exist
            # Note: DuckDB supports indexes but they're automatically managed in many cases
            # These explicit indexes help with query planning and performance

            # Index on coin column for partition lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crypto_prices_coin
                ON raw.crypto_prices (coin)
            """)

            # Index on recorded_at for time range queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crypto_prices_recorded_at
                ON raw.crypto_prices (recorded_at)
            """)

            # Composite index for coin + time range queries (most common pattern)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crypto_prices_coin_recorded_at
                ON raw.crypto_prices (coin, recorded_at)
            """)

            # Index on ingested_at for data freshness queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crypto_prices_ingested_at
                ON raw.crypto_prices (ingested_at)
            """)

            # Analyze table to update statistics for query optimizer
            conn.execute("ANALYZE raw.crypto_prices")

    except duckdb.Error as e:
        # Index creation failures are not critical - log but don't fail
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to create performance indexes: {str(e)}")
    except Exception as e:
        # Unexpected errors - log but don't fail the pipeline
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error creating performance indexes: {str(e)}")


def optimize_database() -> None:
    """Optimize database performance and storage.

    Performs maintenance operations to keep the database running efficiently:
    - Vacuum operation to reclaim space
    - Update table statistics for query optimizer
    - Check for and clean up any orphaned data

    This function should be called periodically (e.g., daily) as part of maintenance.
    """
    try:
        if not DUCKDB_PATH.exists():
            return

        with duckdb.connect(str(DUCKDB_PATH)) as conn:
            # Vacuum to reclaim space and optimize storage
            conn.execute("VACUUM raw.crypto_prices")

            # Update table statistics for better query planning
            conn.execute("ANALYZE raw.crypto_prices")

            # Remove any potential duplicates (defensive check)
            conn.execute("""
                DELETE FROM raw.crypto_prices
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM raw.crypto_prices
                    GROUP BY coin, recorded_at
                )
            """)

    except duckdb.Error as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Database optimization failed: {str(e)}")
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error during database optimization: {str(e)}")
