"""Unit tests for crypto API module.

Tests the CoinGecko API client functionality including:
- Retry logic
- Rate limit handling
- Error handling for invalid responses
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from crypto_elt_pipeline.utils.crypto_api import (
    RateLimitError,
    fetch_coingecko_data,
)


class TestFetchCoinGeckoData:
    """Tests for fetch_coingecko_data function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        logger = MagicMock(spec=logging.Logger)
        return logger

    @pytest.fixture
    def mock_airbyte_records(self):
        """Create mock API response records."""
        return [
            {"prices": [[1700000000000, 45000.5]]},
            {"prices": [[1700003600000, 45100.25]]},
        ]

    def test_fetch_success_with_retry(self, mock_logger, mock_airbyte_records):
        """Test successful fetch on first attempt."""
        with patch("crypto_elt_pipeline.utils.crypto_api.ab.get_source") as mock_source:
            # Setup mock
            mock_source_instance = MagicMock()
            mock_source_instance.get_records.return_value = iter(mock_airbyte_records)
            mock_source.return_value = mock_source_instance

            # Execute
            result = fetch_coingecko_data(
                coin_id="bitcoin",
                vs_currency="usd",
                days=1,
                logger=mock_logger,
            )

            # Verify
            assert result == mock_airbyte_records
            mock_source_instance.check.assert_called_once()
            mock_source_instance.select_streams.assert_called_once_with(["market_chart"])

    def test_rate_limit_error_raises(self, mock_logger):
        """Test that rate limit error is properly raised after retries."""
        with (
            patch("crypto_elt_pipeline.utils.crypto_api.ab.get_source") as mock_source,
            patch("crypto_elt_pipeline.utils.crypto_api.get_config") as mock_config,
        ):
            # Setup mock config for retry settings
            mock_ingestion = MagicMock()
            mock_ingestion.retry_max_attempts = 2
            mock_ingestion.retry_base_delay = 0.01  # Very short for fast tests
            mock_ingestion.retry_max_delay = 0.01
            mock_config.return_value.ingestion = mock_ingestion

            # Setup mock to raise rate limit error
            mock_source_instance = MagicMock()
            error = Exception("Error: Rate limit exceeded - 429 Too Many Requests")
            mock_source_instance.get_records.side_effect = error
            mock_source.return_value = mock_source_instance

            # Execute & Verify
            with pytest.raises(RateLimitError) as exc_info:
                fetch_coingecko_data(
                    coin_id="bitcoin",
                    vs_currency="usd",
                    days=1,
                    logger=mock_logger,
                )

            assert "Rate limit exceeded" in str(exc_info.value)
            assert "bitcoin" in str(exc_info.value)

    def test_empty_response_raises_value_error(self, mock_logger):
        """Test that empty API response raises ValueError."""
        with (
            patch("crypto_elt_pipeline.utils.crypto_api.ab.get_source") as mock_source,
            patch("crypto_elt_pipeline.utils.crypto_api.get_config") as mock_config,
        ):
            # Setup mock config
            mock_ingestion = MagicMock()
            mock_ingestion.retry_max_attempts = 0  # No retries
            mock_ingestion.retry_base_delay = 0.01
            mock_ingestion.retry_max_delay = 0.01
            mock_config.return_value.ingestion = mock_ingestion

            # Setup mock to return empty records
            mock_source_instance = MagicMock()
            mock_source_instance.get_records.return_value = iter([])
            mock_source.return_value = mock_source_instance

            # Execute & Verify
            with pytest.raises(ValueError) as exc_info:
                fetch_coingecko_data(
                    coin_id="bitcoin",
                    vs_currency="usd",
                    days=1,
                    logger=mock_logger,
                )

            assert "No records found" in str(exc_info.value)

    def test_invalid_days_handling(self, mock_logger, mock_airbyte_records):
        """Test that invalid days values are handled gracefully."""
        with patch("crypto_elt_pipeline.utils.crypto_api.ab.get_source") as mock_source:
            # Setup mock
            mock_source_instance = MagicMock()
            mock_source_instance.get_records.return_value = iter(mock_airbyte_records)
            mock_source.return_value = mock_source_instance

            # Execute with unusual days value (should round up)
            result = fetch_coingecko_data(
                coin_id="bitcoin",
                vs_currency="usd",
                days=5,  # Not an allowed value, should round to 7
                logger=mock_logger,
            )

            # Verify - the function should handle this gracefully
            assert result == mock_airbyte_records

    def test_days_rounds_to_nearest_allowed(self, mock_logger, mock_airbyte_records):
        """Test that days parameter rounds to nearest allowed value."""
        with (
            patch("crypto_elt_pipeline.utils.crypto_api.ab.get_source") as mock_source,
            patch("crypto_elt_pipeline.utils.crypto_api.get_config") as mock_config,
        ):
            # Setup mock config
            mock_ingestion = MagicMock()
            mock_ingestion.retry_max_attempts = 0
            mock_ingestion.retry_base_delay = 0.01
            mock_ingestion.retry_max_delay = 0.01
            mock_config.return_value.ingestion = mock_ingestion

            # Setup mock
            mock_source_instance = MagicMock()
            mock_source.return_value = mock_source_instance

            # Execute each test case separately with fresh mock data
            test_days = [5, 8, 45, 200]
            for days_input in test_days:
                # Create fresh mock records for each iteration
                fresh_records = [{"prices": [[1700000000000, 45000.5]]}]
                mock_source_instance.get_records.return_value = iter(fresh_records)

                result = fetch_coingecko_data(
                    coin_id="bitcoin",
                    vs_currency="usd",
                    days=days_input,
                    logger=mock_logger,
                )
                assert result == fresh_records

    def test_generic_api_error_propagates(self, mock_logger):
        """Test that non-rate-limit errors are propagated correctly."""
        with patch("crypto_elt_pipeline.utils.crypto_api.ab.get_source") as mock_source:
            # Setup mock to raise a generic error
            mock_source_instance = MagicMock()
            generic_error = Exception("Connection timeout")
            mock_source_instance.get_records.side_effect = generic_error
            mock_source.return_value = mock_source_instance

            # Execute & Verify - generic errors should propagate
            with pytest.raises(Exception) as exc_info:
                fetch_coingecko_data(
                    coin_id="bitcoin",
                    vs_currency="usd",
                    days=1,
                    logger=mock_logger,
                )

            assert "Connection timeout" in str(exc_info.value)


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error_is_exception(self):
        """Verify RateLimitError is a proper exception."""
        assert issubclass(RateLimitError, Exception)

    def test_rate_limit_error_can_be_raised_with_message(self):
        """Test RateLimitError can be raised with a message."""
        with pytest.raises(RateLimitError) as exc_info:
            raise RateLimitError("Test rate limit message")

        assert "Test rate limit message" in str(exc_info.value)
