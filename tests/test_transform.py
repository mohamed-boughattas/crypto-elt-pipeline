"""Tests for data transformation functions.

This module tests the core transformation logic including:
- Unnesting nested market data
- Resampling to hourly granularity
- Merging existing and new data
- Schema validation
"""

import pendulum
import polars as pl
import pytest
from pandera.errors import SchemaError

from crypto_elt_pipeline.utils.crypto_transform import (
    RawMarketChartSchema,
    merge_data,
    resample_to_hourly,
    unnest_market_data,
    validate_enhanced_data,
    validate_raw_data,
)


class TestUnnestMarketData:
    """Tests for unnest_market_data function."""

    def test_empty_raw_data(self):
        """When raw data is empty, should return empty DataFrame with correct schema."""
        raw_df = pl.DataFrame(
            schema={
                "prices": pl.List(pl.List(pl.Float64)),
                "market_caps": pl.List(pl.List(pl.Float64)),
                "total_volumes": pl.List(pl.List(pl.Float64)),
            }
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Should return empty DataFrame with correct schema
        assert result.is_empty()
        expected_columns = [
            "coin",
            "currency",
            "ingested_at",
            "recorded_at",
            "price",
            "market_cap",
            "volume",
        ]
        assert list(result.columns) == expected_columns
        assert result["coin"].dtype == pl.String
        assert result["currency"].dtype == pl.String
        assert result["price"].dtype == pl.Float64
        assert result["market_cap"].dtype == pl.Float64
        assert result["volume"].dtype == pl.Float64

    def test_single_data_point(self):
        """Test with single data point in nested structure."""
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

        # Should return single row
        assert result.height == 1
        assert result["coin"].item() == "bitcoin"
        assert result["currency"].item() == "usd"
        assert result["price"].item() == 45000.50
        assert result["market_cap"].item() == 850000000000.0
        assert result["volume"].item() == 25000000000.0

    def test_multiple_data_points(self):
        """Test with multiple data points in nested structure."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [
                        [1700000000000.0, 45000.50],
                        [1700003600000.0, 45100.25],
                        [1700014400000.0, 45200.00],
                    ],
                ],
                "market_caps": [
                    [
                        [1700000000000.0, 850000000000.0],
                        [1700003600000.0, 852000000000.0],
                        [1700014400000.0, 853000000000.0],
                    ],
                ],
                "total_volumes": [
                    [
                        [1700000000000.0, 25000000000.0],
                        [1700003600000.0, 25500000000.0],
                        [1700014400000.0, 26000000000.0],
                    ],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Should return 3 rows
        assert result.height == 3

        # Verify all columns are present and have correct values
        assert list(result["coin"]) == ["bitcoin"] * 3
        assert list(result["currency"]) == ["usd"] * 3
        assert list(result["price"]) == [45000.50, 45100.25, 45200.00]

        # Verify timestamps are in chronological order
        timestamps = result["recorded_at"].to_list()
        assert timestamps == sorted(timestamps)

    def test_different_coins(self):
        """Test with different cryptocurrency."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 2500.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 300000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 15000000000.0]],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "ethereum", "usd")

        assert result.height == 1
        assert result["coin"].item() == "ethereum"
        assert result["price"].item() == 2500.50

    def test_different_currency(self):
        """Test with different currency."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 42000.00]],
                ],
                "market_caps": [
                    [[1700000000000.0, 800000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 20000000000.0]],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "eur")

        assert result.height == 1
        assert result["currency"].item() == "eur"


class TestResampleToHourly:
    """Tests for resample_to_hourly function."""

    def _create_test_df(self, timestamps: list) -> pl.DataFrame:
        """Helper to create test DataFrame with given timestamps."""
        return pl.DataFrame(
            {
                "coin": ["bitcoin"] * len(timestamps),
                "currency": ["usd"] * len(timestamps),
                "ingested_at": [pendulum.now("UTC")] * len(timestamps),
                "recorded_at": timestamps,
                "price": [50000.0 + i * 100.0 for i in range(len(timestamps))],
                "market_cap": [1e12] * len(timestamps),
                "volume": [1e10] * len(timestamps),
            },
            schema={
                "coin": pl.String,
                "currency": pl.String,
                "ingested_at": pl.Datetime,
                "recorded_at": pl.Datetime,
                "price": pl.Float64,
                "market_cap": pl.Float64,
                "volume": pl.Float64,
            },
        )

    def test_empty_dataframe(self):
        """Empty DataFrame should return empty."""
        df = pl.DataFrame(
            schema={
                "coin": pl.String,
                "currency": pl.String,
                "ingested_at": pl.Datetime,
                "recorded_at": pl.Datetime,
                "price": pl.Float64,
                "market_cap": pl.Float64,
                "volume": pl.Float64,
            }
        )
        result = resample_to_hourly(df)
        assert result.is_empty()

    def test_single_hour(self):
        """Single hour of data should remain unchanged."""
        ts = pendulum.datetime(2026, 1, 1, 12, 0, 0)
        df = self._create_test_df([ts])
        result = resample_to_hourly(df)
        assert result.height == 1

    def test_multiple_hours(self):
        """Multiple hours should produce multiple records."""
        timestamps = [
            pendulum.datetime(2026, 1, 1, 12, 0, 0),
            pendulum.datetime(2026, 1, 1, 13, 0, 0),
            pendulum.datetime(2026, 1, 1, 14, 0, 0),
        ]
        df = self._create_test_df(timestamps)
        result = resample_to_hourly(df)
        assert result.height == 3

    def test_resample_5min_to_hourly(self):
        """5-minute data should be resampled to hourly."""
        timestamps = [
            pendulum.datetime(2026, 1, 1, 12, 0, 0),
            pendulum.datetime(2026, 1, 1, 12, 5, 0),
            pendulum.datetime(2026, 1, 1, 12, 10, 0),
            pendulum.datetime(2026, 1, 1, 12, 15, 0),
        ]
        df = self._create_test_df(timestamps)
        result = resample_to_hourly(df)
        assert result.height == 1
        # Should use LAST price
        assert result["price"].item() == 50300.0

    def test_uses_last_price(self):
        """Should use last price in the hour (closing price)."""
        timestamps = [
            pendulum.datetime(2026, 1, 1, 12, 0, 0),
            pendulum.datetime(2026, 1, 1, 12, 30, 0),
            pendulum.datetime(2026, 1, 1, 12, 59, 0),
        ]
        df = self._create_test_df(timestamps)
        result = resample_to_hourly(df)
        assert result["price"].item() == 50200.0


class TestMergeData:
    """Tests for merge_data function."""

    def _create_test_df(
        self,
        records: list[tuple[str, str, pendulum.DateTime, pendulum.DateTime, float, float, float]],
    ) -> pl.DataFrame:
        """Helper to create test DataFrame."""
        return pl.DataFrame(
            {
                "coin": [r[0] for r in records],
                "currency": [r[1] for r in records],
                "ingested_at": [r[2] for r in records],
                "recorded_at": [r[3] for r in records],
                "price": [r[4] for r in records],
                "market_cap": [r[5] for r in records],
                "volume": [r[6] for r in records],
            },
            schema={
                "coin": pl.String,
                "currency": pl.String,
                "ingested_at": pl.Datetime,
                "recorded_at": pl.Datetime,
                "price": pl.Float64,
                "market_cap": pl.Float64,
                "volume": pl.Float64,
            },
        )

    def test_empty_existing(self):
        """When existing is empty, should return new data."""
        existing = self._create_test_df([])
        new = self._create_test_df(
            [["bitcoin", "usd", pendulum.now("UTC"), pendulum.now("UTC"), 50000.0, 1e12, 1e10]]
        )
        result = merge_data(existing, new)
        assert result.height == 1

    def test_empty_new(self):
        """When new is empty, should return existing data."""
        existing = self._create_test_df(
            [["bitcoin", "usd", pendulum.now("UTC"), pendulum.now("UTC"), 50000.0, 1e12, 1e10]]
        )
        new = self._create_test_df([])
        result = merge_data(existing, new)
        assert result.height == 1

    def test_deduplication(self):
        """Should deduplicate by recorded_at, keeping new data."""
        ts = pendulum.datetime(2026, 1, 1, 12, 0, 0)
        existing = self._create_test_df([["bitcoin", "usd", ts, ts, 50000.0, 1e12, 1e10]])
        new = self._create_test_df([["bitcoin", "usd", ts, ts, 51000.0, 1e12, 1e10]])
        result = merge_data(existing, new)
        assert result.height == 1
        assert result["price"].item() == 51000.0

    def test_concatenation(self):
        """Should concatenate different timestamps."""
        ts1 = pendulum.datetime(2026, 1, 1, 12, 0, 0)
        ts2 = pendulum.datetime(2026, 1, 1, 13, 0, 0)
        existing = self._create_test_df([["bitcoin", "usd", ts1, ts1, 50000.0, 1e12, 1e10]])
        new = self._create_test_df([["bitcoin", "usd", ts2, ts2, 51000.0, 1e12, 1e10]])
        result = merge_data(existing, new)
        assert result.height == 2


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_raw_schema_valid(self):
        """Test valid raw data passes schema validation."""
        df = pl.DataFrame(
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
        result = RawMarketChartSchema.validate(df)
        assert result is not None

    def test_validate_raw_data_empty_raises(self):
        """Empty raw DataFrame raises ValueError."""
        empty_df = pl.DataFrame(
            schema={
                "prices": pl.List(pl.List(pl.Float64)),
                "market_caps": pl.List(pl.List(pl.Float64)),
                "total_volumes": pl.List(pl.List(pl.Float64)),
            }
        )
        with pytest.raises(ValueError, match="empty"):
            validate_raw_data(empty_df)

    def test_validate_raw_data_invalid_schema_raises(self):
        """Invalid schema raises ValueError."""
        bad_df = pl.DataFrame(
            {
                "prices": [["not nested"]],
            },
            strict=False,
        )
        with pytest.raises(ValueError, match="validation failed"):
            validate_raw_data(bad_df)

    def test_validate_enhanced_data_negative_price_raises(self):
        """Negative price in enhanced data raises SchemaError."""
        bad_df = pl.DataFrame(
            {
                "coin": ["bitcoin"],
                "currency": ["usd"],
                "ingested_at": [pendulum.now("UTC")],
                "recorded_at": [pendulum.now("UTC")],
                "price": [-50.0],
                "market_cap": [1e12],
                "volume": [1e10],
            }
        )
        with pytest.raises(SchemaError):
            validate_enhanced_data(bad_df)

    def test_unnest_multi_row_raises(self):
        """Multi-row DataFrame raises ValueError."""
        multi_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                    [[1700003600000.0, 45100.25]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                    [[1700003600000.0, 852000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                    [[1700003600000.0, 25500000000.0]],
                ],
            },
            strict=False,
        )
        with pytest.raises(ValueError, match="Expected exactly 1 row"):
            unnest_market_data(multi_df, "bitcoin", "usd")

    def test_unnest_mismatched_lengths_raises(self):
        """Mismatched list lengths raise ValueError."""
        mismatch_df = pl.DataFrame(
            {
                "prices": [[[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]]],
                "market_caps": [[[1700000000000.0, 850000000000.0]]],  # Only 1 item
                "total_volumes": [[[1700000000000.0, 25000000000.0]]],
            },
            strict=False,
        )
        with pytest.raises(ValueError, match="Data length mismatch"):
            unnest_market_data(mismatch_df, "bitcoin", "usd")
