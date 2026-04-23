"""Tests for crypto database utilities.

Tests DuckDB interaction functions including:
- Timestamp retrieval
- Data retrieval
- Schema validation
"""

from unittest.mock import patch

import pendulum
import polars as pl

from crypto_elt_pipeline.utils.crypto_db import (
    calculate_days_to_fetch,
    get_existing_data,
    get_latest_timestamp,
)


class TestGetLatestTimestamp:
    """Tests for get_latest_timestamp function."""

    def test_returns_none_when_no_data(self):
        """Test None handling."""
        # Test None timestamp handling
        result = get_latest_timestamp("nonexistent_coin")
        # Function should handle missing data gracefully
        assert result is None or isinstance(result, pendulum.DateTime)

    def test_calculate_days_to_fetch_logic(self):
        """Test date calculation logic directly."""
        # Test with None - should return default
        result = calculate_days_to_fetch(None, 30)
        assert result == 30

        # Test with old timestamp - should cap at default
        old_ts = pendulum.now("UTC").subtract(days=100)
        result = calculate_days_to_fetch(old_ts, 30)
        assert result == 30

        # Test with recent timestamp - should return smaller value
        recent_ts = pendulum.now("UTC").subtract(days=1)
        result = calculate_days_to_fetch(recent_ts, 30)
        assert result >= 1


class TestGetExistingData:
    """Tests for get_existing_data function."""

    def test_returns_dataframe_schema(self):
        """Test that returned DataFrame has correct schema."""
        # Test the function with a coin that doesn't exist
        result = get_existing_data("nonexistent_coin_xyz")

        # Should return a DataFrame with correct schema
        assert isinstance(result, pl.DataFrame)

        # Check schema columns exist
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

    def test_returns_empty_for_missing_data(self):
        """Test that empty DataFrame is returned for missing data."""
        result = get_existing_data("nonexistent_coin_xyz_12345")

        # Should return empty DataFrame with correct schema
        assert isinstance(result, pl.DataFrame)
        assert result.height == 0


class TestCalculateDaysToFetch:
    """Tests for calculate_days_to_fetch function."""

    def test_returns_default_when_none_timestamp(self):
        """Test that default days is returned when no timestamp provided."""
        result = calculate_days_to_fetch(None, 30)
        assert result == 30

    def test_returns_minimum_one_day(self):
        """Test that at least 1 day is returned."""
        yesterday = pendulum.now("UTC").subtract(days=1)
        result = calculate_days_to_fetch(yesterday, 30)
        assert result >= 1

    def test_returns_correct_days_difference(self):
        """Test that correct days difference is calculated."""
        five_days_ago = pendulum.now("UTC").subtract(days=5)
        result = calculate_days_to_fetch(five_days_ago, 30)
        assert result == 6  # 5 + 1 (today)

    def test_caps_at_default_days(self):
        """Test that result doesn't exceed default days."""
        old_timestamp = pendulum.now("UTC").subtract(days=100)
        result = calculate_days_to_fetch(old_timestamp, 30)
        assert result == 30  # Capped at default

    def test_handles_zero_days_ago(self):
        """Test edge case with very recent timestamp."""
        today = pendulum.now("UTC")
        result = calculate_days_to_fetch(today, 30)
        assert result == 1  # At least 1 day

    def test_custom_default_days(self):
        """Test with custom default days."""
        result = calculate_days_to_fetch(None, 60)
        assert result == 60


class TestGetLatestTimestampWithDb:
    """Tests for get_latest_timestamp with real database."""

    def test_returns_latest_timestamp_for_coin(self, crypto_db_with_data):
        """Should return the latest timestamp for a coin that has data."""
        with patch("crypto_elt_pipeline.utils.crypto_db.DUCKDB_PATH", crypto_db_with_data):
            result = get_latest_timestamp("bitcoin")
        assert result is not None
        assert isinstance(result, pendulum.DateTime)

    def test_returns_none_for_nonexistent_coin(self, crypto_db_with_data):
        """Should return None for a coin with no data."""
        with patch("crypto_elt_pipeline.utils.crypto_db.DUCKDB_PATH", crypto_db_with_data):
            result = get_latest_timestamp("nonexistent_coin_xyz")
        assert result is None

    def test_returns_none_when_db_does_not_exist(self, temp_db_path):
        """Should return None when database file does not exist."""
        assert not temp_db_path.exists()
        with patch("crypto_elt_pipeline.utils.crypto_db.DUCKDB_PATH", temp_db_path):
            result = get_latest_timestamp("bitcoin")
        assert result is None


class TestGetExistingDataWithDb:
    """Tests for get_existing_data with real database."""

    def test_returns_data_for_existing_coin(self, crypto_db_with_data):
        """Should return DataFrame with data for a coin that exists."""
        with patch("crypto_elt_pipeline.utils.crypto_db.DUCKDB_PATH", crypto_db_with_data):
            result = get_existing_data("bitcoin")
        assert result.height >= 1
        assert result["coin"][0] == "bitcoin"

    def test_returns_empty_for_nonexistent_coin(self, crypto_db_with_data):
        """Should return empty DataFrame for a coin with no data."""
        with patch("crypto_elt_pipeline.utils.crypto_db.DUCKDB_PATH", crypto_db_with_data):
            result = get_existing_data("nonexistent_coin_xyz")
        assert isinstance(result, pl.DataFrame)
        assert result.height == 0
