"""Database connection and data fetching utilities."""

import logging

import duckdb
import pendulum
import polars as pl
import streamlit as st

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.constants import DUCKDB_PATH
from streamlit_dashboard.config import CACHE_TTL

logger = logging.getLogger(__name__)


class DataError(Exception):
    """Custom exception for data-related errors."""

    pass


def check_database_exists() -> bool:
    if not DUCKDB_PATH.exists():
        st.error(f"❌ Database not found at: {DUCKDB_PATH}")
        st.info("💡 Generate data first: `make pipeline`")
        return False
    return True


def check_gold_layer_ready() -> bool:
    try:
        conn = get_connection()
        result = conn.execute("SELECT COUNT(*) FROM mart.fct_crypto_candlesticks").fetchone()
        if result and result[0] > 0:
            return True
        st.error("❌ Gold layer tables are empty. Run `make pipeline` to load data.")
        st.info("💡 The pipeline creates: Bronze → Silver → Gold layers")
        return False
    except Exception as e:
        st.error(f"❌ Error checking Gold layer: {str(e)}")
        st.info("💡 Run `make pipeline` to create the database and load data.")
        return False


@st.cache_resource
def _create_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def get_connection() -> duckdb.DuckDBPyConnection:
    if not check_database_exists():
        st.stop()
    try:
        return _create_connection()
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.stop()


@st.cache_data(ttl=CACHE_TTL)
def get_available_coins() -> list:
    conn = get_connection()
    try:
        df = conn.execute(
            "SELECT DISTINCT coin FROM mart.fct_crypto_candlesticks ORDER BY coin"
        ).pl()
        return df["coin"].to_list()
    except Exception as e:
        logger.error(f"Database error while fetching available coins: {str(e)}", exc_info=True)
        st.error(f"Database error while fetching available coins: {str(e)}")
        st.warning("⚠️ Unable to fetch coin list from database. Using fallback list.")
        return ["bitcoin"]


@st.cache_data(ttl=CACHE_TTL)
def get_coin_colors() -> dict[str, str]:
    return get_config().coin_colors


@st.cache_data(ttl=CACHE_TTL)
def get_market_data(coin: str, start: pendulum.Date, end: pendulum.Date) -> pl.DataFrame:
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
                bb_position,
                daily_change_pct,
                price_range,
                rsi,
                macd,
                macd_signal,
                macd_histogram
            FROM mart.fct_crypto_candlesticks
            WHERE coin = $1
            AND trade_date >= $2
            AND trade_date <= $3
            ORDER BY trade_date
        """
        df = conn.execute(query, [coin, str(start), str(end)]).pl()

        if df.is_empty():
            raise DataError(f"No data available for {coin} in the selected date range.")

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
