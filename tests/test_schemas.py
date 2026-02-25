"""Unit tests for Pandera schema validation."""

import pendulum
import polars as pl
import pytest
from pandera.errors import SchemaError

from crypto_elt_pipeline.defs.assets.ingestion import (
    EnhancedMarketSchema,
    RawMarketChartSchema,
)


class TestRawMarketChartSchema:
    """Tests for RawMarketChartSchema validation."""

    def test_valid_raw_data_passes(self):
        """Verify valid raw data passes schema validation."""
        df = pl.DataFrame(
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
        validated = RawMarketChartSchema.validate(df)
        assert validated is not None

    def test_missing_prices_column_fails(self):
        """Verify missing prices column raises SchemaError."""
        df = pl.DataFrame(
            {
                "market_caps": [[[1700000000000.0, 850000000000.0]]],
                "total_volumes": [[[1700000000000.0, 25000000000.0]]],
            },
            strict=False,
        )
        with pytest.raises(SchemaError):
            RawMarketChartSchema.validate(df)

    def test_missing_market_caps_column_fails(self):
        """Verify missing market_caps column raises SchemaError."""
        df = pl.DataFrame(
            {
                "prices": [[[1700000000000.0, 45000.50]]],
                "total_volumes": [[[1700000000000.0, 25000000000.0]]],
            },
            strict=False,
        )
        with pytest.raises(SchemaError):
            RawMarketChartSchema.validate(df)

    def test_missing_total_volumes_column_fails(self):
        """Verify missing total_volumes column raises SchemaError."""
        df = pl.DataFrame(
            {
                "prices": [[[1700000000000.0, 45000.50]]],
                "market_caps": [[[1700000000000.0, 850000000000.0]]],
            },
            strict=False,
        )
        with pytest.raises(SchemaError):
            RawMarketChartSchema.validate(df)

    def test_extra_columns_allowed(self):
        """Verify extra columns are allowed (strict=False)."""
        df = pl.DataFrame(
            {
                "prices": [[[1700000000000.0, 45000.50]]],
                "market_caps": [[[1700000000000.0, 850000000000.0]]],
                "total_volumes": [[[1700000000000.0, 25000000000.0]]],
                "extra_column": ["some_value"],
            },
            strict=False,
        )
        validated = RawMarketChartSchema.validate(df)
        assert validated is not None

    def test_empty_dataframe_passes(self):
        """Verify empty dataframe with correct schema passes."""
        # Note: Polars infers Null type for empty lists, so we need to provide
        # explicit schema to match the expected List(List(Float64)) type
        df = pl.DataFrame(
            {
                "prices": pl.Series([], dtype=pl.List(pl.List(pl.Float64))),
                "market_caps": pl.Series([], dtype=pl.List(pl.List(pl.Float64))),
                "total_volumes": pl.Series([], dtype=pl.List(pl.List(pl.Float64))),
            }
        )
        # Empty DF should pass schema validation
        validated = RawMarketChartSchema.validate(df)
        assert validated.height == 0


class TestEnhancedMarketSchema:
    """Tests for EnhancedMarketSchema validation with business logic."""

    def test_valid_flattened_data_passes(self):
        """Verify valid flattened data passes schema validation."""
        df = pl.DataFrame(
            {
                "coin": ["bitcoin", "bitcoin"],
                "currency": ["usd", "usd"],
                "ingested_at": [
                    pendulum.datetime(2024, 1, 1, 12, 0, 0),
                    pendulum.datetime(2024, 1, 1, 12, 0, 0),
                ],
                "recorded_at": [
                    pendulum.datetime(2024, 1, 1, 0, 0, 0),
                    pendulum.datetime(2024, 1, 1, 1, 0, 0),
                ],
                "price": [45000.50, 45100.25],
                "market_cap": [850000000000.0, 852000000000.0],
                "volume": [25000000000.0, 25500000000.0],
            }
        )
        validated = EnhancedMarketSchema.validate(df)
        assert validated is not None
        assert validated.height == 2

    def test_missing_coin_column_fails(self):
        """Verify missing coin column raises SchemaError."""
        df = pl.DataFrame(
            {
                "currency": ["usd"],
                "ingested_at": [pendulum.datetime(2024, 1, 1, 12, 0, 0)],
                "recorded_at": [pendulum.datetime(2024, 1, 1, 0, 0, 0)],
                "price": [45000.50],
                "market_cap": [850000000000.0],
                "volume": [25000000000.0],
            }
        )
        # This should fail due to missing required column
        with pytest.raises((SchemaError, pl.exceptions.ColumnNotFoundError)):
            EnhancedMarketSchema.validate(df)

    def test_missing_price_column_fails(self):
        """Verify missing price column raises SchemaError."""
        df = pl.DataFrame(
            {
                "coin": ["bitcoin"],
                "currency": ["usd"],
                "ingested_at": [pendulum.datetime(2024, 1, 1, 12, 0, 0)],
                "recorded_at": [pendulum.datetime(2024, 1, 1, 0, 0, 0)],
                "market_cap": [850000000000.0],
                "volume": [25000000000.0],
            }
        )
        # This should fail due to missing required column
        with pytest.raises((SchemaError, pl.exceptions.ColumnNotFoundError)):
            EnhancedMarketSchema.validate(df)

    def test_negative_price_fails(self):
        """Verify negative prices fail business logic validation."""
        df = pl.DataFrame(
            {
                "coin": ["bitcoin"],
                "currency": ["usd"],
                "ingested_at": [pendulum.datetime(2024, 1, 1, 12, 0, 0)],
                "recorded_at": [pendulum.datetime(2024, 1, 1, 0, 0, 0)],
                "price": [-1.0],  # Negative price should fail
                "market_cap": [850000000000.0],
                "volume": [25000000000.0],
            }
        )
        with pytest.raises(SchemaError):
            EnhancedMarketSchema.validate(df)

    def test_zero_volume_fails(self):
        """Verify zero volume fails business logic validation."""
        df = pl.DataFrame(
            {
                "coin": ["bitcoin"],
                "currency": ["usd"],
                "ingested_at": [pendulum.datetime(2024, 1, 1, 12, 0, 0)],
                "recorded_at": [pendulum.datetime(2024, 1, 1, 0, 0, 0)],
                "price": [45000.50],
                "market_cap": [850000000000.0],
                "volume": [0.0],  # Zero volume should fail
            }
        )
        with pytest.raises(SchemaError):
            EnhancedMarketSchema.validate(df)

    def test_extra_columns_allowed(self):
        """Verify extra columns are allowed (strict=False)."""
        df = pl.DataFrame(
            {
                "coin": ["bitcoin"],
                "currency": ["usd"],
                "ingested_at": [pendulum.datetime(2024, 1, 1, 12, 0, 0)],
                "recorded_at": [pendulum.datetime(2024, 1, 1, 0, 0, 0)],
                "price": [45000.50],
                "market_cap": [850000000000.0],
                "volume": [25000000000.0],
                "extra_column": ["some_value"],
            }
        )
        validated = EnhancedMarketSchema.validate(df)
        assert validated is not None
