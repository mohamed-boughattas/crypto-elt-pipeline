"""Database connection and data fetching utilities.

This module provides functions for connecting to DuckDB and fetching
market data for the dashboard.
"""

import logging
from pathlib import Path

import duckdb
import pendulum
import polars as pl
import streamlit as st

from crypto_elt_pipeline.config import get_config

# Configure logging
logger = logging.getLogger(__name__)

# Cache TTL in seconds (1 hour)
CACHE_TTL = 3600


# --- DATA INFRASTRUCTURE ---
class DataError(Exception):
    """Custom exception for data-related errors with user-friendly messages."""

    pass


def get_db_path() -> Path:
    """Get the path to the DuckDB database."""
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "crypto.duckdb"


def check_database_exists() -> bool:
    """Check if the database exists and is accessible.

    Returns True if the database exists, False otherwise.
    This function is NOT cached to allow recovery after DB is created.
    """
    db_path = get_db_path()

    if not db_path.exists():
        st.error(f"❌ Database not found at: {db_path}")
        st.info("💡 Generate data first: `make pipeline`")
        return False

    return True


def check_gold_layer_ready() -> bool:
    """Verify Gold layer has data before rendering dashboard.

    Returns True if Gold layer tables are populated, False otherwise.
    This function is NOT cached to allow recovery after data is loaded.
    """
    try:
        # Create a new connection for this check to avoid caching issues
        db_path = get_db_path()
        conn = duckdb.connect(str(db_path), read_only=True)
        result = conn.execute("SELECT COUNT(*) FROM mart.fct_crypto_candlesticks").fetchone()
        conn.close()

        if result and result[0] > 0:
            return True
        else:
            st.error("❌ Gold layer tables are empty. Run `make pipeline` to load data.")
            st.info("💡 The pipeline creates: Bronze → Silver → Gold layers")
            return False
    except Exception as e:
        st.error(f"❌ Error checking Gold layer: {str(e)}")
        st.info("💡 Run `make pipeline` to create the database and load data.")
        return False


@st.cache_resource
def _create_connection() -> duckdb.DuckDBPyConnection:
    """Creates a cached, read-only connection to the DuckDB warehouse.

    This function only creates the connection - error handling is done
    separately to avoid caching exceptions in the cached resource.
    """
    db_path = get_db_path()
    return duckdb.connect(str(db_path), read_only=True)


def get_connection() -> duckdb.DuckDBPyConnection:
    """Get a connection to the DuckDB database.

    Performs existence check before attempting to connect.
    """
    if not check_database_exists():
        st.stop()

    try:
        return _create_connection()
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.stop()


@st.cache_data(ttl=CACHE_TTL)
def get_available_coins() -> list:
    """Fetches list of available coins from the database."""
    conn = get_connection()
    try:
        query = "SELECT DISTINCT coin FROM mart.fct_crypto_candlesticks ORDER BY coin"
        df = conn.execute(query).pl()
        return df["coin"].to_list()
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Database error while fetching available coins: {str(e)}", exc_info=True)
        st.error(f"Database error while fetching available coins: {str(e)}")
        st.warning("⚠️ Unable to fetch coin list from database. Using fallback list.")
        return ["bitcoin"]  # Fallback


@st.cache_data(ttl=CACHE_TTL)
def get_coin_colors() -> dict[str, str]:
    """Get coin colors from configuration."""
    return get_config().coin_colors


@st.cache_data(ttl=CACHE_TTL)
def get_market_data(coin: str, start: pendulum.Date, end: pendulum.Date) -> pl.DataFrame:
    """Fetches OHLCV and volatility from the dbt mart layer for a specific coin.

    Args:
        coin: Cryptocurrency identifier (e.g., 'bitcoin')
        start: Start date for the analysis period
        end: End date for the analysis period

    Returns:
        Polars DataFrame with OHLCV data and computed metrics

    Raises:
        DataError: If data is unavailable or stale, with user-friendly message.
    """
    conn = get_connection()
    try:
        query = """
            SELECT
                trade_date,
                coin,
                open_price,
                high_price,
                low_price,
                close_price,
                daily_volume,
                volatility_pct,
                sma_7,
                sma_25,
                bb_middle,
                bb_upper,
                bb_lower,
                bb_width,
                bb_position
            FROM mart.fct_crypto_candlesticks
            WHERE coin = $1
            AND trade_date >= $2
            AND trade_date <= $3
            ORDER BY trade_date
        """
        df = conn.execute(query, [coin, str(start), str(end)]).pl()

        if df.is_empty():
            raise DataError(f"No data available for {coin} in the selected date range.")

        # Validate required columns
        required_cols = [
            "trade_date",
            "coin",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "daily_volume",
        ]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise DataError(f"Missing required columns: {missing_cols}")

        # Validate data quality
        if df["close_price"].null_count() > 0:
            st.warning(f"⚠️ Found {df['close_price'].null_count()} null prices in {coin} data")

        if (df["close_price"] <= 0).any():
            st.warning("⚠️ Found non-positive prices in data")

        return df

    except DataError:
        raise
    except Exception as e:
        st.error(f"❌ Error fetching market data for {coin}: {str(e)}")
        raise DataError(f"Unable to fetch {coin} market data. Please try again.") from e
