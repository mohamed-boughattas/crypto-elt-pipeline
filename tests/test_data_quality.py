"""Essential data quality tests for the crypto ELT pipeline.

This module implements core data quality validation tests that ensure:
- Data integrity and consistency
- Business rule validation
- Schema compliance

Tests are simplified for local development without external dependencies.
"""

from crypto_elt_pipeline.utils.crypto_transform import unnest_market_data


class TestDataIntegrity:
    """Core data integrity validation tests."""

    def test_data_integrity_constraints(self, sample_raw_market_data):
        """Test core data integrity constraints."""
        result = unnest_market_data(sample_raw_market_data, "bitcoin", "usd")

        assert not result.is_empty()
        assert result["price"].min() > 0
        assert result["market_cap"].min() > 0
        assert result["volume"].min() > 0
        assert result["coin"].n_unique() == 1
        assert result["currency"].n_unique() == 1

    def test_ohlc_consistency(self, sample_raw_market_data):
        """Test that OHLC values are logically consistent."""
        result = unnest_market_data(sample_raw_market_data, "bitcoin", "usd")

        assert (result["price"] > 0).all()

    def test_temporal_data_quality(self, sample_raw_market_data):
        """Test temporal data quality and consistency."""
        result = unnest_market_data(sample_raw_market_data, "bitcoin", "usd")

        timestamps = result["recorded_at"].to_list()
        assert timestamps == sorted(timestamps)
        assert result["recorded_at"].n_unique() == result.height


class TestBusinessRules:
    """Tests for business rule validation."""

    def test_positive_prices(self, sample_raw_market_data):
        """Test that all prices are positive."""
        result = unnest_market_data(sample_raw_market_data, "bitcoin", "usd")
        assert (result["price"] > 0).all()

    def test_positive_market_cap(self, sample_raw_market_data):
        """Test that all market caps are positive."""
        result = unnest_market_data(sample_raw_market_data, "bitcoin", "usd")
        assert (result["market_cap"] > 0).all()

    def test_positive_volume(self, sample_raw_market_data):
        """Test that all volumes are positive."""
        result = unnest_market_data(sample_raw_market_data, "bitcoin", "usd")
        assert (result["volume"] > 0).all()

    def test_data_completeness(self, sample_raw_market_data):
        """Test that no null values exist in critical columns."""
        result = unnest_market_data(sample_raw_market_data, "bitcoin", "usd")

        assert result["coin"].null_count() == 0
        assert result["currency"].null_count() == 0
        assert result["price"].null_count() == 0
        assert result["market_cap"].null_count() == 0
        assert result["volume"].null_count() == 0
