"""Unit tests for ingestion module."""

import pendulum
import polars as pl

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.defs.assets.ingestion import (
    CRYPTO_PARTITIONS,
    IngestionConfig,
    calculate_days_to_fetch,
    merge_data,
    resample_to_hourly,
)


class TestIngestionConfig:
    """Tests for IngestionConfig."""

    def test_default_values(self):
        """Verify default configuration values come from config file."""
        config = IngestionConfig()
        # When None, the get_* methods should return values from config file
        assert config.get_vs_currency() == "usd"
        assert config.get_days_to_fetch() == 30

    def test_custom_values(self):
        """Verify custom configuration values."""
        config = IngestionConfig(vs_currency="eur", days_to_fetch=60)
        assert config.vs_currency == "eur"
        assert config.days_to_fetch == 60


class TestCryptoPartitions:
    """Tests for CRYPTO_PARTITIONS definition."""

    def test_partition_keys(self):
        """Verify expected partition keys exist."""
        keys = CRYPTO_PARTITIONS.get_partition_keys()
        # Check a sample of the 10 coins
        assert "bitcoin" in keys
        assert "ethereum" in keys
        assert "solana" in keys
        assert "cardano" in keys
        assert "dogecoin" in keys  # New coin added

    def test_partition_count(self):
        """Verify correct number of partitions matches enabled coins in config."""
        from crypto_elt_pipeline.config import get_config

        config = get_config()
        keys = CRYPTO_PARTITIONS.get_partition_keys()
        assert len(keys) == len(config.enabled_coins)


class TestRawDataStructure:
    """Tests for raw nested data structure from CoinGecko API."""

    def test_nested_list_structure(self):
        """Verify raw data has expected nested list structure."""
        # This is the raw structure from CoinGecko API
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

        # Verify structure
        assert raw_df.height == 1
        assert "prices" in raw_df.columns
        assert "market_caps" in raw_df.columns
        assert "total_volumes" in raw_df.columns

    def test_metadata_columns_added(self):
        """Verify metadata columns are added to raw data."""
        raw_df = pl.DataFrame(
            {
                "prices": [[[1700000000000.0, 45000.50]]],
                "market_caps": [[[1700000000000.0, 850000000000.0]]],
                "total_volumes": [[[1700000000000.0, 25000000000.0]]],
            },
            strict=False,
        )

        # Simulate the metadata column addition from the asset
        final_df = raw_df.with_columns(
            [
                pl.lit("bitcoin").cast(pl.String).alias("coin"),
                pl.lit("usd").cast(pl.String).alias("currency"),
                pl.lit(pendulum.now("UTC")).alias("ingested_at"),
            ]
        )

        assert "coin" in final_df.columns
        assert "currency" in final_df.columns
        assert "ingested_at" in final_df.columns
        assert final_df["coin"].item() == "bitcoin"
        assert final_df["currency"].item() == "usd"


class TestPartitionValidation:
    """Tests for partition key validation."""

    def test_valid_partition_keys(self):
        """Verify valid partition keys are accepted."""
        config = get_config()
        valid_keys = CRYPTO_PARTITIONS.get_partition_keys()
        for key in valid_keys:
            assert key in config.coin_ids

    def test_invalid_partition_key(self):
        """Verify invalid partition key would be rejected."""
        valid_keys = CRYPTO_PARTITIONS.get_partition_keys()
        invalid_key = "invalid_coin_xyz"
        assert invalid_key not in valid_keys


class TestDateCalculation:
    """Tests for date range calculations."""

    def test_date_range_calculation(self):
        """Verify date range is calculated correctly."""
        days = 30
        now = pendulum.now("UTC")

        start_date = now.subtract(days=days).strftime("%d-%m-%Y")
        end_date = now.add(days=1).strftime("%d-%m-%Y")

        assert len(start_date) == 10  # DD-MM-YYYY
        assert len(end_date) == 10

    def test_start_date_in_past(self):
        """Verify start date is in the past."""
        days = 30
        now = pendulum.now("UTC")
        start_date = now.subtract(days=days).strftime("%d-%m-%Y")

        # Parse back to datetime
        parsed_start = pendulum.parse(start_date, strict=False)
        assert parsed_start < now


class TestDataPointCounting:
    """Tests for counting data points in nested lists."""

    def test_data_point_count(self):
        """Verify correct counting of nested data points."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]],
                    [[1700007200000.0, 45200.00]],  # Different number of points
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0], [1700003600000.0, 852000000000.0]],
                    [[1700007200000.0, 853000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0], [1700003600000.0, 25500000000.0]],
                    [[1700007200000.0, 26000000000.0]],
                ],
            },
            strict=False,
        )

        # Count total data points (sum of list lengths)
        total_points = raw_df.select(pl.col("prices").list.len().sum()).item()
        assert total_points == 3  # 2 + 1


class TestCalculateDaysToFetch:
    """Tests for calculate_days_to_fetch function."""

    def test_no_existing_data(self):
        """When no existing data, should return default days."""
        result = calculate_days_to_fetch(None, 30)
        assert result == 30

    def test_recent_data(self):
        """When data is recent (1 hour ago), should fetch 1 day."""
        recent_timestamp = pendulum.now("UTC").subtract(hours=1)
        result = calculate_days_to_fetch(recent_timestamp, 30)
        assert result == 1

    def test_one_day_old_data(self):
        """When data is 1 day old, should fetch 2 days."""
        old_timestamp = pendulum.now("UTC").subtract(days=1)
        result = calculate_days_to_fetch(old_timestamp, 30)
        assert result == 2

    def test_week_old_data(self):
        """When data is 7 days old, should fetch 8 days."""
        old_timestamp = pendulum.now("UTC").subtract(days=7)
        result = calculate_days_to_fetch(old_timestamp, 30)
        assert result == 8

    def test_caps_at_default(self):
        """When gap exceeds default, should cap at default."""
        very_old_timestamp = pendulum.now("UTC").subtract(days=100)
        result = calculate_days_to_fetch(very_old_timestamp, 30)
        assert result == 30


class TestMergeData:
    """Tests for merge_data function."""

    def _create_test_df(
        self,
        records: list[tuple[str, str, pendulum.DateTime, pendulum.DateTime, float, float, float]],
    ) -> pl.DataFrame:
        """Helper to create test DataFrame.

        Args:
            records: List of tuples containing (coin, currency, ingested_at, recorded_at, price, market_cap, volume)

        Returns:
            Polars DataFrame with the test data
        """
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
        existing = self._create_test_df(
            [
                ["bitcoin", "usd", ts, ts, 50000.0, 1e12, 1e10]  # Old price
            ]
        )
        new = self._create_test_df(
            [
                ["bitcoin", "usd", ts, ts, 51000.0, 1e12, 1e10]  # New price (same timestamp)
            ]
        )
        result = merge_data(existing, new)
        assert result.height == 1
        assert result["price"].item() == 51000.0  # New price wins

    def test_concatenation(self):
        """Should concatenate different timestamps."""
        ts1 = pendulum.datetime(2026, 1, 1, 12, 0, 0)
        ts2 = pendulum.datetime(2026, 1, 1, 13, 0, 0)
        existing = self._create_test_df([["bitcoin", "usd", ts1, ts1, 50000.0, 1e12, 1e10]])
        new = self._create_test_df([["bitcoin", "usd", ts2, ts2, 51000.0, 1e12, 1e10]])
        result = merge_data(existing, new)
        assert result.height == 2


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
                "price": [50000.0 + i * 100 for i in range(len(timestamps))],
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
        # 12:00, 12:05, 12:10, 12:15 -> all become 12:00
        timestamps = [
            pendulum.datetime(2026, 1, 1, 12, 0, 0),
            pendulum.datetime(2026, 1, 1, 12, 5, 0),
            pendulum.datetime(2026, 1, 1, 12, 10, 0),
            pendulum.datetime(2026, 1, 1, 12, 15, 0),
        ]
        df = self._create_test_df(timestamps)
        result = resample_to_hourly(df)
        assert result.height == 1  # All 4 records become 1 hour
        # Should use LAST price (50000 + 3*100 = 50300)
        assert result["price"].item() == 50300.0

    def test_uses_last_price(self):
        """Should use last price in the hour (closing price)."""
        timestamps = [
            pendulum.datetime(2026, 1, 1, 12, 0, 0),  # price: 50000
            pendulum.datetime(2026, 1, 1, 12, 30, 0),  # price: 50100
            pendulum.datetime(2026, 1, 1, 12, 59, 0),  # price: 50200 (last)
        ]
        df = self._create_test_df(timestamps)
        result = resample_to_hourly(df)
        assert result["price"].item() == 50200.0  # Last price wins
