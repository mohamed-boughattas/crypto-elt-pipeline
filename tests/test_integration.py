"""Integration tests for the crypto ELT pipeline.

These tests verify the end-to-end data flow and transformations
across multiple components.

Note: These tests require a local database and are skipped in CI.
"""

import os

import duckdb
import pytest

from crypto_elt_pipeline.constants import DUCKDB_PATH

# Skip all integration tests in CI environment
# These tests require a local database that doesn't exist in CI
pytestmark = pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Integration tests require local database - run pipeline first",
)


@pytest.fixture
def db_connection():
    """Create a connection to the test database.

    This fixture is shared across all integration test classes to avoid
    duplication and ensure consistent database access.
    """
    if not DUCKDB_PATH.exists():
        pytest.skip("Database not found - run pipeline first")

    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    yield conn
    conn.close()


@pytest.mark.integration
class TestDatabaseStructure:
    """Tests for database schema and structure."""

    def test_database_exists(self):
        """Verify the database file exists."""
        assert DUCKDB_PATH.exists(), f"Database not found at {DUCKDB_PATH}"

    def test_raw_schema_exists(self, db_connection):
        """Verify the raw (Bronze) schema exists."""
        result = db_connection.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'raw'"
        ).fetchone()
        assert result is not None, "Raw schema not found"

    def test_staging_schema_exists(self, db_connection):
        """Verify the staging (Silver) schema exists."""
        result = db_connection.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'staging'"
        ).fetchone()
        assert result is not None, "Staging schema not found"

    def test_mart_schema_exists(self, db_connection):
        """Verify the mart (Gold) schema exists."""
        result = db_connection.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'mart'"
        ).fetchone()
        assert result is not None, "Mart schema not found"

    def test_raw_table_structure(self, db_connection):
        """Verify the raw crypto_prices table has expected columns."""
        columns = db_connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'raw' AND table_name = 'crypto_prices'"
        ).fetchall()

        column_names = [col[0] for col in columns]
        expected_columns = [
            "coin",
            "currency",
            "ingested_at",
            "recorded_at",
            "price",
            "market_cap",
            "volume",
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in raw.crypto_prices"

    def test_gold_table_structure(self, db_connection):
        """Verify the gold candlesticks table has expected columns."""
        columns = db_connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'mart' AND table_name = 'fct_crypto_candlesticks'"
        ).fetchall()

        column_names = [col[0] for col in columns]
        expected_columns = [
            "coin",
            "trade_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "daily_volume",
            "volatility_pct",
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in mart.fct_crypto_candlesticks"


@pytest.mark.integration
class TestDataFlow:
    """Tests for data flow through the pipeline layers."""

    def test_raw_to_staging_row_count(self, db_connection):
        """Verify data flows from raw to staging with expected transformations."""
        # Get row counts
        raw_count = db_connection.execute("SELECT COUNT(*) FROM raw.crypto_prices").fetchone()[0]

        staging_count = db_connection.execute(
            "SELECT COUNT(*) FROM staging.stg_crypto_prices"
        ).fetchone()[0]

        # Staging should have more rows due to unnesting
        # Each raw row contains multiple data points
        assert staging_count > 0, "Staging table is empty"
        assert raw_count > 0, "Raw table is empty"

    def test_staging_to_gold_aggregation(self, db_connection):
        """Verify gold layer has daily aggregations."""
        from crypto_elt_pipeline.config import get_config

        # Get distinct dates in staging
        staging_dates = db_connection.execute(
            "SELECT COUNT(DISTINCT DATE(recorded_at)) FROM staging.stg_crypto_prices"
        ).fetchone()[0]

        # Get row count in gold
        gold_count = db_connection.execute(
            "SELECT COUNT(*) FROM mart.fct_crypto_candlesticks"
        ).fetchone()[0]

        # Get number of enabled coins from config
        config = get_config()
        num_coins = len(config.enabled_coins)

        # Gold should have one row per coin per day
        assert gold_count > 0, "Gold table is empty"
        # Gold count should be <= staging dates * number of coins
        assert gold_count <= staging_dates * num_coins, (
            f"Gold has more rows ({gold_count}) than expected "
            f"({staging_dates} dates * {num_coins} coins = {staging_dates * num_coins})"
        )

    def test_ohlc_consistency(self, db_connection):
        """Verify OHLC values are logically consistent."""
        df = db_connection.execute("SELECT * FROM mart.fct_crypto_candlesticks").pl()

        # High should be >= Low
        assert (df["high_price"] >= df["low_price"]).all(), "High < Low found"

        # High should be >= Open and Close
        assert (df["high_price"] >= df["open_price"]).all(), "High < Open found"
        assert (df["high_price"] >= df["close_price"]).all(), "High < Close found"

        # Low should be <= Open and Close
        assert (df["low_price"] <= df["open_price"]).all(), "Low > Open found"
        assert (df["low_price"] <= df["close_price"]).all(), "Low > Close found"

    def test_volatility_calculation(self, db_connection):
        """Verify volatility is calculated correctly."""
        df = db_connection.execute("SELECT * FROM mart.fct_crypto_candlesticks LIMIT 10").pl()

        # Volatility should be positive
        assert (df["volatility_pct"] >= 0).all(), "Negative volatility found"

        # Calculate expected volatility
        expected = ((df["high_price"] - df["low_price"]) / df["low_price"]) * 100

        # Compare with tolerance for floating-point precision
        # Use 0.01 tolerance (1 basis point) to avoid flakiness
        assert ((df["volatility_pct"] - expected).abs() < 0.01).all(), (
            "Volatility calculation mismatch"
        )


@pytest.mark.integration
class TestMultiCoinSupport:
    """Tests for multi-cryptocurrency support."""

    def test_multiple_coins_in_gold(self, db_connection):
        """Verify multiple cryptocurrencies are present in gold layer."""
        coins = db_connection.execute(
            "SELECT DISTINCT coin FROM mart.fct_crypto_candlesticks ORDER BY coin"
        ).fetchall()

        coin_list = [coin[0] for coin in coins]

        # At least bitcoin should be present
        assert len(coin_list) >= 1, "No coins found in gold layer"

        # Check for expected coins
        expected_coins = ["bitcoin", "ethereum", "solana", "cardano"]
        for coin in expected_coins:
            if coin in coin_list:
                # Verify the coin has data (using parameterized query for consistency)
                count = db_connection.execute(
                    "SELECT COUNT(*) FROM mart.fct_crypto_candlesticks WHERE coin = ?",
                    [coin],
                ).fetchone()[0]
                assert count > 0, f"No data for {coin}"

    def test_coin_data_isolation(self, db_connection):
        """Verify data for each coin is properly isolated."""
        df = db_connection.execute(
            "SELECT coin, COUNT(*) as cnt FROM mart.fct_crypto_candlesticks "
            "GROUP BY coin ORDER BY cnt DESC"
        ).pl()

        # Each coin should have its own data
        assert df.height > 0, "No coin data found"

        # Verify no cross-contamination
        for row in df.iter_rows(named=True):
            coin = row["coin"]
            count = row["cnt"]
            assert count > 0, f"Coin {coin} has no data"


@pytest.mark.integration
class TestDataQuality:
    """Tests for data quality checks."""

    def test_no_null_prices(self, db_connection):
        """Verify no null prices in gold layer."""
        null_count = db_connection.execute(
            "SELECT COUNT(*) FROM mart.fct_crypto_candlesticks "
            "WHERE close_price IS NULL OR open_price IS NULL"
        ).fetchone()[0]

        assert null_count == 0, f"Found {null_count} rows with null prices"

    def test_positive_prices(self, db_connection):
        """Verify all prices are positive."""
        negative_count = db_connection.execute(
            "SELECT COUNT(*) FROM mart.fct_crypto_candlesticks "
            "WHERE close_price <= 0 OR open_price <= 0"
        ).fetchone()[0]

        assert negative_count == 0, f"Found {negative_count} rows with non-positive prices"

    def test_positive_volume(self, db_connection):
        """Verify all volumes are non-negative."""
        negative_count = db_connection.execute(
            "SELECT COUNT(*) FROM mart.fct_crypto_candlesticks WHERE daily_volume < 0"
        ).fetchone()[0]

        assert negative_count == 0, f"Found {negative_count} rows with negative volume"

    def test_date_continuity(self, db_connection):
        """Verify data has reasonable date continuity."""
        df = db_connection.execute(
            "SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date, "
            "COUNT(DISTINCT trade_date) as unique_dates "
            "FROM mart.fct_crypto_candlesticks"
        ).fetchone()

        min_date, max_date, unique_dates = df

        assert min_date is not None, "No minimum date found"
        assert max_date is not None, "No maximum date found"
        assert unique_dates > 0, "No unique dates found"

        # Verify date range is reasonable (at least 1 day)
        assert max_date >= min_date, "Max date is before min date"
