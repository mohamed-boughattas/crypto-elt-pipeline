"""Unit tests for crypto database utilities.

Tests the DuckDB interaction functions including:
- Timestamp retrieval
- Data retrieval
- Edge cases for missing database/tables
"""

from unittest.mock import MagicMock, patch

import pendulum
import polars as pl

from crypto_elt_pipeline.utils.crypto_db import (
    calculate_days_to_fetch,
    get_existing_data,
    get_latest_timestamp,
)


class TestGetLatestTimestamp:
    """Tests for get_latest_timestamp function."""

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    def test_returns_latest_timestamp(self, mock_connect):
        """Test that latest timestamp is returned correctly."""
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (pendulum.datetime(2024, 1, 15, 12, 0, 0),)
        mock_conn.execute.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        # Execute
        result = get_latest_timestamp("bitcoin")

        # Verify
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        mock_conn.execute.assert_called_once()

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    def test_returns_none_when_no_data(self, mock_connect):
        """Test that None is returned when no data exists for coin."""
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (None,)
        mock_conn.execute.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        # Execute
        result = get_latest_timestamp("bitcoin")

        # Verify
        assert result is None

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    def test_returns_none_when_database_not_found(self, mock_connect):
        """Test that None is returned when database file doesn't exist."""
        # Setup mock to raise FileNotFoundError
        mock_connect.side_effect = FileNotFoundError("Database not found")

        # Execute
        result = get_latest_timestamp("bitcoin")

        # Verify
        assert result is None

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    def test_returns_none_on_duckdb_error(self, mock_connect):
        """Test that None is returned when DuckDB raises an error."""
        # Setup mock to raise DuckDB error
        import duckdb

        mock_connect.side_effect = duckdb.Error("Table not found")

        # Execute
        result = get_latest_timestamp("bitcoin")

        # Verify
        assert result is None


class TestGetExistingData:
    """Tests for get_existing_data function."""

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    @patch("crypto_elt_pipeline.utils.crypto_db.get_config")
    def test_returns_data_with_records(self, mock_config, mock_connect):
        """Test that existing data is returned when records exist."""
        # Setup config mock
        mock_ingestion = MagicMock()
        mock_ingestion.history_days = 365
        mock_config.return_value.ingestion = mock_ingestion

        # Setup DB mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (
                "bitcoin",
                "usd",
                pendulum.datetime(2024, 1, 1),
                pendulum.datetime(2024, 1, 1),
                45000.0,
                850000000000.0,
                25000000000.0,
            ),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        # Execute
        result = get_existing_data("bitcoin")

        # Verify
        assert isinstance(result, pl.DataFrame)
        assert result.height == 1
        assert "coin" in result.columns
        assert "price" in result.columns

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    @patch("crypto_elt_pipeline.utils.crypto_db.get_config")
    def test_returns_empty_dataframe_when_no_records(self, mock_config, mock_connect):
        """Test that empty DataFrame is returned when no records exist."""
        # Setup config mock
        mock_ingestion = MagicMock()
        mock_ingestion.history_days = 365
        mock_config.return_value.ingestion = mock_ingestion

        # Setup DB mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        # Execute
        result = get_existing_data("bitcoin")

        # Verify
        assert isinstance(result, pl.DataFrame)
        assert result.height == 0
        # Check schema columns exist
        assert "coin" in result.columns
        assert "price" in result.columns

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    @patch("crypto_elt_pipeline.utils.crypto_db.get_config")
    def test_returns_empty_dataframe_on_database_error(self, mock_config, mock_connect):
        """Test that empty DataFrame is returned when database error occurs."""
        # Setup config mock
        mock_ingestion = MagicMock()
        mock_ingestion.history_days = 365
        mock_config.return_value.ingestion = mock_ingestion

        # Setup mock to raise error
        mock_connect.side_effect = FileNotFoundError("Database not found")

        # Execute
        result = get_existing_data("bitcoin")

        # Verify
        assert isinstance(result, pl.DataFrame)
        assert result.height == 0

    @patch("crypto_elt_pipeline.utils.crypto_db.duckdb.connect")
    @patch("crypto_elt_pipeline.utils.crypto_db.get_config")
    def test_uses_correct_schema_columns(self, mock_config, mock_connect):
        """Test that returned DataFrame has correct schema columns."""
        # Setup config mock
        mock_ingestion = MagicMock()
        mock_ingestion.history_days = 365
        mock_config.return_value.ingestion = mock_ingestion

        # Setup DB mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn

        # Execute
        result = get_existing_data("bitcoin")

        # Verify all expected columns exist
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
            assert col in result.columns, f"Missing column: {col}"


class TestCalculateDaysToFetch:
    """Tests for calculate_days_to_fetch function."""

    def test_returns_default_when_none_timestamp(self):
        """Test that default days is returned when no timestamp provided."""
        result = calculate_days_to_fetch(None, 30)
        assert result == 30

    def test_returns_minimum_one_day(self):
        """Test that at least 1 day is returned."""
        # Timestamp from yesterday
        yesterday = pendulum.now("UTC").subtract(days=1)
        result = calculate_days_to_fetch(yesterday, 30)
        # Returns 2 because: days_diff (1) + 1 (today) = 2
        assert result == 2

    def test_returns_correct_days_difference(self):
        """Test that correct days difference is calculated."""
        # Timestamp from 5 days ago
        five_days_ago = pendulum.now("UTC").subtract(days=5)
        result = calculate_days_to_fetch(five_days_ago, 30)
        assert result == 6  # 5 + 1 (today)

    def test_caps_at_default_days(self):
        """Test that result doesn't exceed default days."""
        # Timestamp from very old (more than default)
        old_timestamp = pendulum.now("UTC").subtract(days=100)
        result = calculate_days_to_fetch(old_timestamp, 30)
        assert result == 30  # Capped at default

    def test_handles_zero_days_ago(self):
        """Test edge case with very recent timestamp."""
        # Timestamp from today (0 days ago)
        today = pendulum.now("UTC")
        result = calculate_days_to_fetch(today, 30)
        assert result == 1  # At least 1 day
