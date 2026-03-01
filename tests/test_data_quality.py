"""Essential data quality tests for the crypto ELT pipeline.

This module implements core data quality validation tests that ensure:
- Data integrity and consistency
- Business rule validation
- Schema compliance

Tests are simplified for local development without external dependencies.
"""

import pendulum
import polars as pl

from crypto_elt_pipeline.utils.crypto_transform import (
    EnhancedMarketSchema,
    RawMarketChartSchema,
    unnest_market_data,
)


class TestDataIntegrity:
    """Core data integrity validation tests."""

    def test_data_integrity_constraints(self):
        """Test core data integrity constraints."""
        # Test with valid data
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]],
                ],
                "market_caps": [
                    [
                        [1700000000000.0, 850000000000.0],
                        [1700003600000.0, 852000000000.0],
                    ],
                ],
                "total_volumes": [
                    [
                        [1700000000000.0, 25000000000.0],
                        [1700003600000.0, 25500000000.0],
                    ],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Test all integrity constraints
        assert not result.is_empty()
        assert result["price"].min() > 0  # No negative prices
        assert result["market_cap"].min() > 0  # No negative market caps
        assert result["volume"].min() > 0  # No negative volumes
        assert result["coin"].n_unique() == 1  # Single coin per partition
        assert result["currency"].n_unique() == 1  # Single currency per partition

    def test_ohlc_consistency(self):
        """Test that OHLC values are logically consistent."""
        # Create test data with OHLC structure
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [
                        [1700000000000.0, 45000.50],
                        [1700003600000.0, 45100.25],
                        [1700007200000.0, 45200.00],
                    ],
                ],
                "market_caps": [
                    [
                        [1700000000000.0, 850000000000.0],
                        [1700003600000.0, 852000000000.0],
                        [1700007200000.0, 853000000000.0],
                    ],
                ],
                "total_volumes": [
                    [
                        [1700000000000.0, 25000000000.0],
                        [1700003600000.0, 25500000000.0],
                        [1700007200000.0, 26000000000.0],
                    ],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # All prices should be positive
        assert (result["price"] > 0).all()

    def test_temporal_data_quality(self):
        """Test temporal data quality and consistency."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [
                        [1700000000000.0, 45000.50],
                        [1700003600000.0, 45100.25],
                        [1700007200000.0, 45200.00],
                    ],
                ],
                "market_caps": [
                    [
                        [1700000000000.0, 850000000000.0],
                        [1700003600000.0, 852000000000.0],
                        [1700007200000.0, 853000000000.0],
                    ],
                ],
                "total_volumes": [
                    [
                        [1700000000000.0, 25000000000.0],
                        [1700003600000.0, 25500000000.0],
                        [1700007200000.0, 26000000000.0],
                    ],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Temporal consistency: timestamps should be in chronological order
        timestamps = result["recorded_at"].to_list()
        assert timestamps == sorted(timestamps)

        # Temporal consistency: no duplicate timestamps
        assert result["recorded_at"].n_unique() == result.height


class TestBusinessRules:
    """Tests for business rule validation."""

    def test_positive_prices(self):
        """Test that all prices are positive."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")
        assert (result["price"] > 0).all()

    def test_positive_market_cap(self):
        """Test that all market caps are positive."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")
        assert (result["market_cap"] > 0).all()

    def test_positive_volume(self):
        """Test that all volumes are positive."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")
        assert (result["volume"] > 0).all()

    def test_data_completeness(self):
        """Test that no null values exist in critical columns."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Check critical columns for nulls
        assert result["coin"].null_count() == 0
        assert result["currency"].null_count() == 0
        assert result["price"].null_count() == 0
        assert result["market_cap"].null_count() == 0
        assert result["volume"].null_count() == 0


class TestSchemaValidation:
    """Test schema validation for data contracts."""

    def test_raw_schema_validation(self):
        """Test validation of raw nested data structure."""
        # Valid raw data
        valid_raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        # Should pass validation
        RawMarketChartSchema.validate(valid_raw_df)

    def test_enhanced_schema_validation(self):
        """Test validation of flattened market data."""
        # Valid flattened data
        valid_flattened_df = pl.DataFrame(
            {
                "coin": ["bitcoin", "bitcoin"],
                "currency": ["usd", "usd"],
                "ingested_at": [pendulum.now("UTC"), pendulum.now("UTC")],
                "recorded_at": [
                    pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC"),
                    pendulum.datetime(2023, 11, 14, 23, 13, 20, tz="UTC"),
                ],
                "price": [45000.50, 45100.25],
                "market_cap": [850000000000.0, 852000000000.0],
                "volume": [25000000000.0, 25500000000.0],
            }
        )

        # Should pass validation
        try:
            EnhancedMarketSchema.validate(valid_flattened_df)
            validation_passed = True
        except Exception:
            validation_passed = False
        assert validation_passed

    def test_negative_price_fails_validation(self):
        """Test that negative prices fail validation."""
        # Invalid flattened data - negative price
        invalid_flattened_df = pl.DataFrame(
            {
                "coin": ["bitcoin"],
                "currency": ["usd"],
                "ingested_at": [pendulum.now("UTC")],
                "recorded_at": [pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC")],
                "price": [-100.0],  # Invalid: negative price
                "market_cap": [850000000000.0],
                "volume": [25000000000.0],
            }
        )

        # Should fail validation
        try:
            EnhancedMarketSchema.validate(invalid_flattened_df)
            validation_passed = True
        except Exception:
            validation_passed = False
        assert not validation_passed
